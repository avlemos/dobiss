"""Dobiss Cover (screens/roller shutters) Control"""
import logging
from typing import Dict, List, Optional, Tuple

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .dobiss import DobissSystem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Dobiss Cover platform."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    # Build covers by pairing Up/Down outputs.
    covers: List[Dict] = _pair_covers(coordinator.dobiss.outputs)

    _LOGGER.info("Adding covers (roller shutters/screens)...")
    _LOGGER.debug(str(covers))

    async_add_entities(
        HomeAssistantDobissCover(coordinator, cover) for cover in covers
    )
    _LOGGER.info("Dobiss covers added.")


def _pair_covers(outputs: List[Dict]) -> List[Dict]:
    """Pair Up/Down outputs into single cover descriptors.

    Strategy:
    - Prefer pairing by (moduleAddress, groupIndex), assuming Dobiss assigns the
      same groupIndex to the Up/Down of a single physical cover.
    - If that doesn't yield a pair, fall back to name-based heuristic:
      strip a trailing " up"/" down" suffix (case-insensitive) and pair by base name.
    - As a last resort, any single unpaired Up or Down becomes a one-direction
      cover entity (you will only be able to drive the available direction).
    """
    ups: Dict[Tuple[int, int], Dict] = {}
    downs: Dict[Tuple[int, int], Dict] = {}

    # First pass: index by (moduleAddress, groupIndex)
    for out in outputs:
        if out.get("type") == DobissSystem.OutputType.Up:
            ups[(out["moduleAddress"], out["groupIndex"])] = out
        elif out.get("type") == DobissSystem.OutputType.Down:
            downs[(out["moduleAddress"], out["groupIndex"])] = out

    covers: List[Dict] = []

    processed_keys = set()
    for key, up in ups.items():
        if key in processed_keys:
            continue
        down = downs.get(key)
        if down:
            processed_keys.add(key)
            covers.append(_build_cover_descriptor(up, down))

    # Add any remaining by name heuristic
    def norm_name(n: str) -> str:
        n = (n or "").strip().lower()
        for suffix in (" up", " down"):
            if n.endswith(suffix):
                return n[: -len(suffix)].strip()
        return n

    # Collect leftovers
    leftover_ups = [u for k, u in ups.items() if k not in processed_keys]
    leftover_downs = [d for k, d in downs.items() if k not in processed_keys]

    name_index_up: Dict[str, Dict] = {norm_name(u["name"]): u for u in leftover_ups}
    name_index_down: Dict[str, Dict] = {norm_name(d["name"]): d for d in leftover_downs}

    matched_names = set(name_index_up.keys()) & set(name_index_down.keys())
    for base in matched_names:
        covers.append(_build_cover_descriptor(name_index_up[base], name_index_down[base]))
        # remove so they don't get added as single-direction later
        name_index_up.pop(base, None)
        name_index_down.pop(base, None)

    # Single-direction entities for any remaining
    for u in name_index_up.values():
        covers.append(_build_cover_descriptor(u, None))
    for d in name_index_down.values():
        covers.append(_build_cover_descriptor(None, d))

    return covers


def _build_cover_descriptor(up: Optional[Dict], down: Optional[Dict]) -> Dict:
    """Create a cover descriptor dictionary from Up/Down outputs."""
    name_parts = []
    module_addr = up["moduleAddress"] if up else down["moduleAddress"]
    if up:
        name_parts.append(up.get("name") or "")
    if down and (not up or down.get("name") != up.get("name")):
        name_parts.append(down.get("name") or "")

    # Derive a cleaned base name
    def tidy(n: str) -> str:
        n = (n or "").strip()
        if n.lower().endswith(" up"):
            return n[:-3].strip()
        if n.lower().endswith(" down"):
            return n[:-5].strip()
        return n

    base_name = tidy(up.get("name") if up else down.get("name")) or "Cover"

    # unique id from available components
    uid_parts = [str(module_addr)]
    if up:
        uid_parts.append(f"U{up['index']}")
    if down:
        uid_parts.append(f"D{down['index']}")

    return {
        "moduleAddress": module_addr,
        "name": base_name,
        "up": up,
        "down": down,
        "unique_id": ".".join(uid_parts),
    }


class HomeAssistantDobissCover(CoordinatorEntity, CoverEntity):
    """Representation of a Dobiss cover (screen or roller shutter)."""

    def __init__(self, coordinator, cover: Dict):
        super().__init__(coordinator)
        self.dobiss = coordinator.dobiss
        self._cover = cover
        self._name = cover["name"]

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._cover["unique_id"]

    @property
    def supported_features(self):
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        # We can always stop by switching off both directions
        features |= CoverEntityFeature.STOP
        return features

    @property
    def is_closed(self):
        # Unknown without position feedback
        return None

    @property
    def is_opening(self):
        up = self._cover.get("up")
        if not up:
            return False
        val = self.coordinator.data.get(up["moduleAddress"], [0] * (up["index"] + 1))[up["index"]]
        return val == 100

    @property
    def is_closing(self):
        down = self._cover.get("down")
        if not down:
            return False
        val = self.coordinator.data.get(down["moduleAddress"], [0] * (down["index"] + 1))[down["index"]]
        return val == 100

    async def async_open_cover(self, **kwargs):
        up = self._cover.get("up")
        if not up:
            _LOGGER.warning("No Up output available for cover '%s'", self._name)
            return
        # Ensure Down is off
        await self._turn_dir(off=self._cover.get("down"))
        # Start Up
        await self._turn_dir(on=up)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs):
        down = self._cover.get("down")
        if not down:
            _LOGGER.warning("No Down output available for cover '%s'", self._name)
            return
        # Ensure Up is off
        await self._turn_dir(off=self._cover.get("up"))
        # Start Down
        await self._turn_dir(on=down)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs):
        # Stop by turning both directions off
        await self._turn_dir(off=self._cover.get("up"))
        await self._turn_dir(off=self._cover.get("down"))
        await self.coordinator.async_request_refresh()

    async def _turn_dir(self, on: Optional[Dict] = None, off: Optional[Dict] = None):
        if off:
            await self.dobiss.setOff(off["moduleAddress"], off["index"])
        if on:
            # Use relay-type action: 100% on
            await self.dobiss.setOn(on["moduleAddress"], on["index"], 100)
