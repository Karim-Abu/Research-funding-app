# LIVE LLM SMOKE REPORT

- timestamp_utc: `2026-07-23T19:58:28+00:00`
- status: `failed`
- provider_routes: `not_available`
- model_refs: `not_available`
- preflight_status: `not_available`
- preflight_fingerprints: `not_available`
- execution_mode: `live`
- request_count: `5`
- provider_call_seconds: `not_available`
- active_execution_seconds: `not_available`
- cost_chf: `not_available`
- web_calls: `3`
- web_credits: `not_available`
- fake_fallback_observed: `no`
- reason_code: `live_02a_failed`

## Redacted request ledger

- attempt_id=`521117706f974e72bcb799e34d6bde0d`, request_sequence=`1`, provider=`firecrawl`, route_alias=`firecrawl`, purpose=`public_search`, started_at=`2026-07-23T19:57:30+00:00`, finished_at=`2026-07-23T19:57:33+00:00`, http_class=`2xx`, http_status=`not_available`, retryable=`False`, reason_code=`none`, input_tokens=`None`, output_tokens=`None`, estimated_cost_chf=`not_available`, actual_cost_chf=`not_available`
- attempt_id=`521117706f974e72bcb799e34d6bde0d`, request_sequence=`2`, provider=`firecrawl`, route_alias=`firecrawl`, purpose=`public_fetch`, started_at=`2026-07-23T19:57:33+00:00`, finished_at=`2026-07-23T19:57:35+00:00`, http_class=`2xx`, http_status=`not_available`, retryable=`False`, reason_code=`none`, input_tokens=`None`, output_tokens=`None`, estimated_cost_chf=`not_available`, actual_cost_chf=`not_available`
- attempt_id=`521117706f974e72bcb799e34d6bde0d`, request_sequence=`3`, provider=`firecrawl`, route_alias=`firecrawl`, purpose=`public_fetch`, started_at=`2026-07-23T19:57:36+00:00`, finished_at=`2026-07-23T19:57:49+00:00`, http_class=`2xx`, http_status=`not_available`, retryable=`False`, reason_code=`none`, input_tokens=`None`, output_tokens=`None`, estimated_cost_chf=`not_available`, actual_cost_chf=`not_available`
- attempt_id=`521117706f974e72bcb799e34d6bde0d`, request_sequence=`4`, provider=`openai_direct`, route_alias=`openai_gpt_56_terra_candidate`, purpose=`a2_preflight`, started_at=`2026-07-23T19:58:07+00:00`, finished_at=`2026-07-23T19:58:10+00:00`, http_class=`2xx`, http_status=`not_available`, retryable=`False`, reason_code=`none`, input_tokens=`48`, output_tokens=`17`, estimated_cost_chf=`0.049737`, actual_cost_chf=`0.000303`
- attempt_id=`521117706f974e72bcb799e34d6bde0d`, request_sequence=`5`, provider=`openai_direct`, route_alias=`openai_gpt_56_terra_candidate`, purpose=`live_02a`, started_at=`2026-07-23T19:58:10+00:00`, finished_at=`2026-07-23T19:58:28+00:00`, http_class=`2xx`, http_status=`not_available`, retryable=`False`, reason_code=`none`, input_tokens=`2787`, output_tokens=`1303`, estimated_cost_chf=`0.06867`, actual_cost_chf=`0.021396`
