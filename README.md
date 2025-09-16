[![HACS Compliance](https://github.com/avlemos/dobiss/actions/workflows/validate.yaml/badge.svg "HACS Compliance")]([https://www.markdownguide.org](https://github.com/avlemos/dobiss/actions/workflows/validate.yaml))
[![Validate with hassfest](https://github.com/avlemos/dobiss/actions/workflows/hassfest.yaml/badge.svg "hassfest Compliance")]([https://www.markdownguide.org](https://github.com/avlemos/dobiss/actions/workflows/hassfest.yaml)) 

# Intro

This is a project for [Home Assistant](https://github.com/home-assistant) which enables you to connect to your [Dobiss Ambience PRO](https://products.dobiss.com/nl/onze-oplossingen/per-gamma/ambiance-pro) system, by using the **DO5437** module, which makes a bridge betweent the CAN bus that Dobiss provides, and your network, via an RJ45 interface.


# Usage
With this, you can check the state of the lights, and toggle them. There are other uses for the Dobiss system, but the only hardware I have are the lights, so if you find anything broken outside of lights, feel free to do a PR.

After installing the Integration, you should find a new Dobiss Domotics entry, where you will be able to configure the IP address of the **DO5437** module.

# Fork
This is a fork from [OpenJeDi/HomeAssistantFiles](https://github.com/OpenJeDi/HomeAssistantFiles) without the configuration files (thank you [@OpenJeDi](https://github.com/OpenJeDi) for doing 99.9% of the work).

You can see the fork [here](https://github.com/avlemos/HomeAssistantFiles), which is(was) 4 commits ahead, as of this writing. I only use this for lights, so other elements may be broken.


# Differences
The main differences for this fork are:

1. async usage so that it doesn't bog down on HA (this was the main reason why I forked)
1. HACS compatibility, so it's easier to keep up to date
1. trying to keep up with HA deprecation/new methods


## Polling and state updates

- The integration uses Home Assistant's DataUpdateCoordinator to poll the Dobiss controller for all output states.
- Default polling interval is 10 seconds.
- You can change the polling interval in Home Assistant at any time:
  - Go to Settings > Devices & Services > Dobiss Domotics > Configure > Options.
  - Adjust "Scan interval (seconds)" to your preferred value and save.
- After you operate an entity (turn on/off, set brightness, open/close/stop), the integration also triggers an immediate refresh so the UI updates quickly.
- Each poll opens a short-lived TCP connection to the controller, requests all statuses, and immediately disconnects again. This avoids locking the controller so the official Dobiss Pro app can keep working.

Recommendations:
- For most setups, 5–10 seconds balances responsiveness and controller load well.
- Setting very low intervals (e.g., <3 seconds) may increase network/CPU load and could make the controller less responsive if multiple clients are connected.
