import json
from jinja2 import Template

LOCUST_TEMPLATE = Template('''import os
from pathlib import Path

from locust import HttpUser, between, task

# =========================
# 配置区
# =========================
GATEWAY_BASE_URL = "{{ base_url }}"

{% for item in tasks %}
TASK_WEIGHT_{{ loop.index }} = {{ item.weight }}
{% endfor %}


class PressureUser(HttpUser):
    host = GATEWAY_BASE_URL
    wait_time = between(0.01, 0.05)

{% for item in tasks %}
    @task(TASK_WEIGHT_{{ loop.index }})
    def {{ item.function_name }}(self) -> None:
        path = {{ item.path_expr }}

        headers = {{ item.headers }}

{% if item.body_expr %}
        payload = {{ item.body_expr }}
{% endif %}

        with self.client.request(
            method="{{ item.method }}",
            url=path,
            headers=headers,
{% if item.body_expr %}
            json=payload,
{% endif %}
            name="{{ item.task_name }}",
            catch_response=True,
        ) as resp:
            if resp.status_code not in {200, 201, 202}:
                msg = f"{{ item.function_name }} HTTP " + str(resp.status_code) + " | url=" + path + " | resp=" + resp.text[:500]
                resp.failure(msg)
                print(msg, flush=True)
                return
            try:
                payload = resp.json()
            except ValueError:
                msg = f"{{ item.function_name }} 非 JSON | url=" + path + " | resp=" + resp.text[:500]
                resp.failure(msg)
                print(msg, flush=True)
                return
            if not bool(payload.get("success")):
                msg = f"{{ item.function_name }} 业务失败 success=" + str(payload.get("success")) + " | resp=" + resp.text[:500]
                resp.failure(msg)
                print(msg, flush=True)

{% endfor %}

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    raise SystemExit(os.system("locust -f {{ filename }}"))
''')


def generate_locust_script(endpoints: list[dict], filename: str = "stress_test.py") -> str:
    tasks = []
    for i, ep in enumerate(endpoints):
        function_name = ep.get("name", "").replace(" ", "_") or f"api_{ep.get('id', i)}"
        function_name = "".join(c if c.isalnum() or c == "_" else "_" for c in function_name)

        headers_raw = ep.get("headers", "{}")
        try:
            headers = json.loads(headers_raw)
        except (json.JSONDecodeError, TypeError):
            headers = {}

        body_raw = ep.get("body", "{}")
        has_body = ep.get("method", "GET") == "POST" and body_raw and body_raw != "{}"

        path = ep.get("path", "/")
        query_params = ep.get("query_params", "")
        if query_params:
            path_expr = f'f"{path}?{query_params}"'
        else:
            path_expr = f'"{path}"'

        tasks.append({
            "weight": 1,
            "function_name": function_name,
            "method": ep.get("method", "GET"),
            "path_expr": path_expr,
            "headers": json.dumps(headers, indent=4),
            "body_expr": body_raw if has_body else "",
            "task_name": ep.get("name", path),
        })

    base_url = endpoints[0].get("host", "https://api.example.com") if endpoints else "https://api.example.com"

    return LOCUST_TEMPLATE.render(base_url=base_url, tasks=tasks, filename=filename)
