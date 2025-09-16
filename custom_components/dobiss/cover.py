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
      same groupIndex to the Up/Down of a single physical cover. Support multiple
      covers sharing the same groupIndex by pairing greedily within each key.
    - If that doesn't yield a pair, fall back to name-based heuristic:
      strip a trailing " up"/" down" suffix (case-insensitive) and pair by base name,
      keeping per-module groupings and supporting duplicate names.
    - As a last resort, any single unpaired Up or Down becomes a one-direction
      cover entity (you will only be able to drive the available direction).
    """
    from collections import defaultdict, deque

    def norm_name(n: str) -> str:
        n = (n or "").strip().lower()
        for suffix in (" up", " down"):
            if n.endswith(suffix):
                return n[: -len(suffix)].strip()
        return n

    # First pass: index by (moduleAddress, groupIndex) and keep all entries per key
    ups_map: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
    downs_map: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)

    for out in outputs:
        if out.get("type") == DobissSystem.OutputType.Up:
            ups_map[(out["moduleAddress"], out["groupIndex"])].append(out)
        elif out.get("type") == DobissSystem.OutputType.Down:
            downs_map[(out["moduleAddress"], out["groupIndex"])].append(out)

    covers: List[Dict] = []

    # Greedy pairing within each (module, groupIndex)
    leftover_ups: List[Dict] = []
    leftover_downs: List[Dict] = []

    all_keys = set(ups_map.keys()) | set(downs_map.keys())
    for key in all_keys:
        ups_list = ups_map.get(key, [])
        downs_list = downs_map.get(key, [])
        if ups_list and downs_list:
            # Use name-based pairing first within the key
            ups_by_name: Dict[str, deque] = defaultdict(deque)
            downs_by_name: Dict[str, deque] = defaultdict(deque)
            for u in sorted(ups_list, key=lambda x: x.get("index", 0)):
                ups_by_name[norm_name(u.get("name"))].append(u)
            for d in sorted(downs_list, key=lambda x: x.get("index", 0)):
                downs_by_name[norm_name(d.get("name"))].append(d)

            matched_names = set(ups_by_name.keys()) & set(downs_by_name.keys())
            for nm in sorted(matched_names):
                while ups_by_name[nm] and downs_by_name[nm]:
                    u = ups_by_name[nm].popleft()
                    d = downs_by_name[nm].popleft()
                    covers.append(_build_cover_descriptor(u, d))

            # Collect remaining in lists by index order to pair loosely
            remaining_ups = [u for q in ups_by_name.values() for u in q]
            remaining_downs = [d for q in downs_by_name.values() for d in q]
            remaining_ups.sort(key=lambda x: x.get("index", 0))
            remaining_downs.sort(key=lambda x: x.get("index", 0))

            # Pair by closest indices greedily
            iu = id = 0
            while iu < len(remaining_ups) and id < len(remaining_downs):
                u = remaining_ups[iu]
                d = remaining_downs[id]
                covers.append(_build_cover_descriptor(u, d))
                iu += 1
                id += 1

            # Any remainder goes to global leftovers
            leftover_ups.extend(remaining_ups[iu:])
            leftover_downs.extend(remaining_downs[id:])
        else:
            # Move all to leftovers if only one direction exists under this key
            leftover_ups.extend(ups_list)
            leftover_downs.extend(downs_list)

    # Cross-key name-based pairing while preserving module boundary and supporting duplicates
    from collections import defaultdict as dd
    up_index: Dict[Tuple[int, str], deque] = dd(deque)
    down_index: Dict[Tuple[int, str], deque] = dd(deque)

    for u in sorted(leftover_ups, key=lambda x: (x["moduleAddress"], x.get("index", 0))):
        up_index[(u["moduleAddress"], norm_name(u.get("name")))].append(u)
    for d in sorted(leftover_downs, key=lambda x: (x["moduleAddress"], x.get("index", 0))):
        down_index[(d["moduleAddress"], norm_name(d.get("name")))].append(d)

    common_keys = set(up_index.keys()) & set(down_index.keys())
    for k in sorted(common_keys):
        uq = up_index[k]
        dq = down_index[k]
        while uq and dq:
            covers.append(_build_cover_descriptor(uq.popleft(), dq.popleft()))

    # Single-direction entities for any remaining
    for uq in up_index.values():
        while uq:
            covers.append(_build_cover_descriptor(uq.popleft(), None))
    for dq in down_index.values():
        while dq:
            covers.append(_build_cover_descriptor(None, dq.popleft()))

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
