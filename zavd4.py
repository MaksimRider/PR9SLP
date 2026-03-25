import json
import re


ALLOWED_ENVS = {"dev", "test", "prod"}
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}
ALLOWED_TYPES = {"print", "set", "add", "multiply", "if", "summary"}
ALLOWED_OPS = {"==", "!=", ">", ">=", "<", "<="}


def load_config(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config):
    if "app" not in config:
        raise ValueError("Відсутній блок app")
    if "server" not in config:
        raise ValueError("Відсутній блок server")
    if "features" not in config:
        raise ValueError("Відсутній блок features")
    if "workflow" not in config:
        raise ValueError("Відсутній блок workflow")

    app = config["app"]
    if not isinstance(app.get("name"), str):
        raise TypeError("app.name має бути рядком")
    if not isinstance(app.get("version"), str):
        raise TypeError("app.version має бути рядком")
    if app.get("env") not in ALLOWED_ENVS:
        raise ValueError("app.env має бути dev, test або prod")

    server = config["server"]
    if not isinstance(server.get("host"), str):
        raise TypeError("server.host має бути рядком")
    if not isinstance(server.get("port"), int):
        raise TypeError("server.port має бути цілим числом")
    if not (1 <= server["port"] <= 65535):
        raise ValueError("server.port має бути в межах 1..65535")
    if server.get("logLevel") not in ALLOWED_LOG_LEVELS:
        raise ValueError("server.logLevel має бути debug, info, warning або error")

    features = config["features"]
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
    if "steps" not in workflow:
        raise ValueError("Відсутній workflow.steps")
    if not isinstance(workflow["steps"], list):
        raise TypeError("workflow.steps має бути списком")

    for i, step in enumerate(workflow["steps"], start=1):
        validate_step(step, i)


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

    elif step_type == "set":
        if "var" not in step or "value" not in step:
            raise ValueError(f"Крок {index}: для set потрібні поля var і value")

    elif step_type in ["add", "multiply"]:
        for field in ["var", "a", "b"]:
            if field not in step:
                raise ValueError(f"Крок {index}: для {step_type} потрібне поле {field}")

    elif step_type == "if":
        if "condition" not in step or "then" not in step:
            raise ValueError(f"Крок {index}: для if потрібні поля condition і then")

        condition = step["condition"]
        for field in ["left", "op", "right"]:
            if field not in condition:
                raise ValueError(f"Крок {index}: у condition відсутнє поле {field}")

        if condition["op"] not in ALLOWED_OPS:
            raise ValueError(f"Крок {index}: недопустимий оператор умови")

    elif step_type == "summary":
        if "fields" not in step:
            raise ValueError(f"Крок {index}: для summary потрібне поле fields")


def get_value(value, variables, config):
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{([^}]+)\}", value)
        if match:
            key = match.group(1)

            if "." in key:
                parts = key.split(".")
                current = config
                for part in parts:
                    if part not in current:
                        raise ValueError(f"Значення '{key}' не знайдено в конфігурації")
                    current = current[part]
                return current

            if key not in variables:
                raise ValueError(f"Змінна '{key}' не визначена")
            return variables[key]

    return value


def replace_variables_in_text(text, variables, config):
    def replacer(match):
        key = match.group(1)

        if "." in key:
            parts = key.split(".")
            current = config
            for part in parts:
                if part not in current:
                    raise ValueError(f"Значення '{key}' не знайдено в конфігурації")
                current = current[part]
            return str(current)

        if key not in variables:
            raise ValueError(f"Змінна '{key}' не визначена")
        return str(variables[key])

    return re.sub(r"\$\{([^}]+)\}", replacer, text)


def ensure_number(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"Значення '{name}' не є числом")


def check_condition(condition, variables, config):
    left = get_value(condition["left"], variables, config)
    right = get_value(condition["right"], variables, config)
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

    raise ValueError(f"Невідомий оператор: {op}")


def execute_steps(steps, variables, config):
    for step in steps:
        step_type = step["type"]

        if step_type == "print":
            message = replace_variables_in_text(step["message"], variables, config)
            print(message)

        elif step_type == "set":
            variables[step["var"]] = step["value"]

        elif step_type == "add":
            a = get_value(step["a"], variables, config)
            b = get_value(step["b"], variables, config)
            ensure_number(a, "a")
            ensure_number(b, "b")
            variables[step["var"]] = a + b

        elif step_type == "multiply":
            a = get_value(step["a"], variables, config)
            b = get_value(step["b"], variables, config)
            ensure_number(a, "a")
            ensure_number(b, "b")
            variables[step["var"]] = a * b

        elif step_type == "if":
            if check_condition(step["condition"], variables, config):
                execute_steps(step["then"], variables, config)
            else:
                execute_steps(step.get("else", []), variables, config)

        elif step_type == "summary":
            print("Підсумок:")
            for field in step["fields"]:
                if field not in variables:
                    raise ValueError(f"Змінна '{field}' не визначена")
                print(f"{field} = {variables[field]}")

        else:
            raise ValueError(f"Невідомий тип кроку: {step_type}")


def main():
    try:
        config = load_config("config4.json")
        validate_config(config)

        variables = {}
        execute_steps(config["workflow"]["steps"], variables, config)

    except Exception as error:
        print("Помилка:", error)


if __name__ == "__main__":
    main()