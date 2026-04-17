# Second Environment Feasibility Summary

- Run tag: `second_environment_botiot_feasibility_2026-04-17`
- Verdict: `blocked_bot_iot_official_access_forbidden`
- Reason: BoT-IoT official SharePoint dataset folder is not directly usable from this environment because it returns HTTP 403 or redirects to Microsoft login, and no local BoT-IoT copy is present.

## Official Source Probe
- `BoT-IoT` page: `https://research.unsw.edu.au/projects/bot-iot-dataset`
- `BoT-IoT` official dataset probe status: `200`
- `TON-IoT` page: `https://research.unsw.edu.au/projects/toniot-datasets`
- `TON-IoT` official dataset probe status: `200`

## Local Dataset Probe
- `BoT-IoT` local root provided: `False`
- `BoT-IoT` local root exists: `False`
- `BoT-IoT` labeled candidates: `0`
- `TON-IoT` local root provided: `False`
- `TON-IoT` local root exists: `False`
- `TON-IoT` labeled candidates: `0`

## Next
- Do not start formal second-environment training yet.
- First obtain a local BoT-IoT or TON-IoT dataset copy and rerun this feasibility probe.
