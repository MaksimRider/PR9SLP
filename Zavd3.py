import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


ALLOWED_ENVS = {"dev", "test", "prod"}
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}
ALLOWED_TYPES = {"print", "set", "add", "multiply", "if", "summary"}
ALLOWED_OPS = {"==", "!=", ">", ">=", "<", "<="}


def load_config(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Файл {filename} не знайдено")

    suffix = path.suffix.lower()

    with open(path, "r", encoding="utf-8") as file:
        if suffix == ".json":
            return json.load(file)
        elif suffix in [".yaml", ".yml"]:
            if yaml is None:
                raise ImportError("Для YAML потрібно встановити бібліотеку pyyaml: pip install pyyaml")
            return yaml.safe_load(file)
        else:
            raise ValueError("Підтримуються лише файли .json, .yaml, .yml")


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Конфігурація має бути об'єктом")

    for section in ["app", "server", "features", "workflow"]:
        if section not in config:
            raise ValueError(f"Відсутній обов'язковий блок: {section}")

    app = config["app"]
    if not isinstance(app, dict):
        raise TypeError("app має бути об'єктом")
    if not isinstance(app.get("name"), str):
        raise TypeError("app.name має бути рядком")
    if not isinstance(app.get("version"), str):
        raise TypeError("app.version має бути рядком")
    if app.get("env") not in ALLOWED_ENVS:
        raise ValueError("app.env має бути одним із: dev, test, prod")

    server = config["server"]
    if not isinstance(server, dict):
        raise TypeError("server має бути об'єктом")
    if not isinstance(server.get("host"), str):
        raise TypeError("server.host має бути рядком")
    if not isinstance(server.get("port"), int):
        raise TypeError("server.port має бути цілим числом")
    if not (1 <= server["port"] <= 65535):
        raise ValueError("server.port має бути в межах 1..65535")
    if server.get("logLevel") not in ALLOWED_LOG_LEVELS:
        raise ValueError("server.logLevel має бути одним із: debug, info, warning, error")

    features = config["features"]
    if not isinstance(features, dict):
        raise TypeError("features має бути об'єктом")
    if not isinstance(features.get("enableCache"), bool):
        raise TypeError("features.enableCache має бути bool")
    if not isinstance(features.get("enableMetrics"), bool):
        raise TypeError("features.enableMetrics має бути bool")
    if not isinstance(features.get("experimental"), list):
        raise TypeError("features.experimental має бути списком")

    for item in features["experimental"]:
        if not isinstance(item, str):
            raise TypeError("features.experimental має містити тільки рядки")

    workflow = config["workflow"]
    if not isinstance(workflow, dict):
        raise TypeError("workflow має бути об'єктом")
    if "steps" not in workflow:
        raise ValueError("Відсутній workflow.steps")
    if not isinstance(workflow["steps"], list):
        raise TypeError("workflow.steps має бути списком")

    for index, step in enumerate(workflow["steps"], start=1):
        validate_step(step, index)


def validate_step(step, index):
    if not isinstance(step, dict):
        raise TypeError(f"Крок {index} має бути об'єктом")

    if "type" not in step:
        raise ValueError(f"Крок {index} не містить поле type")

    step_type = step["type"]

    if step_type not in ALLOWED_TYPES:
        raise ValueError(f"Крок {index}: невідомий type '{step_type}'")

    if step_type == "print":
        if "message" not in step:
            raise ValueError(f"Крок {index}: для print потрібне поле message")
        if not isinstance(step["message"], str):
            raise TypeError(f"Крок {index}: message має бути рядком")

    elif step_type == "set":
        if "var" not in step or "value" not in step:
            raise ValueError(f"Крок {index}: для set потрібні поля var і value")
        if not isinstance(step["var"], str):
            raise TypeError(f"Крок {index}: var має бути рядком")

    elif step_type in ["add", "multiply"]:
        for field in ["var", "a", "b"]:
            if field not in step:
                raise ValueError(f"Крок {index}: для {step_type} потрібне поле {field}")
        if not isinstance(step["var"], str):
            raise TypeError(f"Крок {index}: var має бути рядком")

    elif step_type == "if":
        if "condition" not in step or "then" not in step:
            raise ValueError(f"Крок {index}: для if потрібні поля condition і then")
        if not isinstance(step["condition"], dict):
            raise TypeError(f"Крок {index}: condition має бути об'єктом")
        if not isinstance(step["then"], list):
            raise TypeError(f"Крок {index}: then має бути списком")
        if "else" in step and not isinstance(step["else"], list):
            raise TypeError(f"Крок {index}: else має бути списком")

        condition = step["condition"]
        for field in ["left", "op", "right"]:
            if field not in condition:
                raise ValueError(f"Крок {index}: у condition відсутнє поле {field}")

        if condition["op"] not in ALLOWED_OPS:
            raise ValueError(f"Крок {index}: недопустимий оператор умови {condition['op']}")

    elif step_type == "summary":
        if "fields" not in step:
            raise ValueError(f"Крок {index}: для summary потрібне поле fields")
        if not isinstance(step["fields"], list):
            raise TypeError(f"Крок {index}: fields має бути списком")
        for field in step["fields"]:
            if not isinstance(field, str):
                raise TypeError(f"Крок {index}: fields має містити тільки рядки")


def get_value(value, variables):
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{(\w+)\}", value)
        if match:
            var_name = match.group(1)
            if var_name not in variables:
                raise ValueError(f"Помилка виконання: змінна '{var_name}' не визначена")
            return variables[var_name]
    return value


def replace_variables_in_text(text, variables):
    def repl(match):
        var_name = match.group(1)
        if var_name not in variables:
            raise ValueError(f"Помилка виконання: змінна '{var_name}' не визначена")
        return str(variables[var_name])

    return re.sub(r"\$\{(\w+)\}", repl, text)


def ensure_number(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"Помилка виконання: значення '{name}' не є числом")


def check_condition(condition, variables):
    left = get_value(condition["left"], variables)
    right = get_value(condition["right"], variables)
    op = condition["op"]

    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right

    raise ValueError(f"Помилка виконання: невідомий оператор {op}")


def execute_steps(steps, variables):
    for step in steps:
        step_type = step["type"]

        if step_type == "print":
            print(replace_variables_in_text(step["message"], variables))

        elif step_type == "set":
            variables[step["var"]] = step["value"]

        elif step_type == "add":
            a = get_value(step["a"], variables)
            b = get_value(step["b"], variables)
            ensure_number(a, "a")
            ensure_number(b, "b")
            variables[step["var"]] = a + b

        elif step_type == "multiply":
            a = get_value(step["a"], variables)
            b = get_value(step["b"], variables)
            ensure_number(a, "a")
            ensure_number(b, "b")
            variables[step["var"]] = a * b

        elif step_type == "if":
            result = check_condition(step["condition"], variables)
            if result:
                execute_steps(step["then"], variables)
            else:
                execute_steps(step.get("else", []), variables)

        elif step_type == "summary":
            print("Підсумок:")
            for field in step["fields"]:
                if field not in variables:
                    raise ValueError(f"Помилка виконання: змінна '{field}' не визначена")
                print(f"{field} = {variables[field]}")

        else:
            raise ValueError(f"Помилка виконання: невідомий type '{step_type}'")


def main():
    filename = "config3.json"
    if len(sys.argv) > 1:
        filename = sys.argv[1]

    try:
        config = load_config(filename)
        validate_config(config)
        variables = {}
        execute_steps(config["workflow"]["steps"], variables)
    except Exception as error:
        print(f"Помилка: {error}")


if __name__ == "__main__":
    main()