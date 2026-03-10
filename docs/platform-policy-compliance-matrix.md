# Platform Policy Compliance Matrix (MVP)

Ovaj dokument definira osnovna MVP pravila za validaciju sadržaja prije schedulinga po platformi.

| Platform | Max chars | Blocked terms (primjeri) | Connected account required | Enforcement |
|---|---:|---|---|---|
| Instagram | 2200 | `guaranteed`, `100% cure`, `instant results` | Da | `platform_policy_check` + `schedule_publish` guard |
| LinkedIn | 3000 | `guaranteed`, `no risk` | Da | `platform_policy_check` + `schedule_publish` guard |
| TikTok | 2200 | `guaranteed`, `instant results` | Ne | `platform_policy_check` |
| YouTube | 5000 | `100% cure`, `guaranteed` | Ne | `platform_policy_check` |

## API endpoints

- `GET /v1/content/{workspace_id}/platform-policy-matrix`
- `GET /v1/content/{workspace_id}/platform-policy-check?item_id=...&platform=...`

## Notes

- Ova pravila su baseline za MVP i ne predstavljaju potpunu pravnu/policy usklađenost svake platforme.
- Produkcijska verzija treba uključiti detaljniju policy klasifikaciju i redovan update pravila.
