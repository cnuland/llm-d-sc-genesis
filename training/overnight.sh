#!/usr/bin/env bash
# Unattended: wait for the Qwen3.8 endpoint, prove it returns usable content,
# then run generate -> cross-verify -> train -> evaluate for cost and sensitivity.
set -uo pipefail
cd "$(dirname "$0")"
URL=https://llama-server-qwen38-homelab-maas.apps.ironman.cjlabs.dev
KEY=$(cat /tmp/.maaskey)

echo "[overnight] waiting for qwen38 to serve..."
for i in $(seq 1 360); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -H "Authorization: Bearer $KEY" "$URL/v1/models" 2>/dev/null)
  [ "$code" = "200" ] && { echo "[overnight] endpoint up after $((i*20))s"; break; }
  sleep 20
done

# A 200 on /v1/models only proves the process is listening. The failure that
# actually matters is an empty `content` (all budget spent on reasoning), which
# would silently generate zero rows, so prove real output BEFORE committing to
# a multi-hour run.
echo "[overnight] smoke-testing generation..."
SMOKE=$(python3 - <<'PY'
import sys; sys.argv=['x','cost']
exec(open('sdg_llm.py').read().replace('if __name__ == "__main__":','if False:'))
url, model = QWEN
items = clean(parse_list(call(url, model, gen_prompt('cost','LOW',TAXONOMIES['cost']['tiers']['LOW'],'clock repair','real_world'))),'LOW')
print(len(items))
PY
)
echo "[overnight] smoke test produced ${SMOKE} prompts"
if [ "${SMOKE:-0}" -lt 3 ]; then
  echo "[overnight] ABORT: qwen38 is not returning usable content."
  echo "[overnight] Falling back to DS4 as the generator so the night is not wasted."
  python3 - <<'PY'
p='sdg_llm.py'; s=open(p).read()
s=s.replace('GENERATORS = [QWEN]','GENERATORS = [DS4]')
open(p,'w').write(s)
p='verify.py'; s=open(p).read()
s=s.replace('url, model = (QWEN if "ds4" in gen else DS4)','url, model = (QWEN if "ds4" in gen else DS4)')
open(p,'w').write(s)
print("switched generator to DS4")
PY
fi

exec ./pipeline.sh
