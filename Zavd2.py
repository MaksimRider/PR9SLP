import json
import re


ALLOWED_ENVS = {"dev", "test", "prod"}
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}


def load_config(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config):
    if "app" not in config:
        raise ValueError("Відсутній розділ app")
    if "server" not in config:
        raise ValueError("Відсутній розділ server")
    if "features" not in config:
        raise ValueError("Відсутній розділ features")
    if "workflow" not in config:
        raise ValueError("Відсутній розділ workflow")

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


def get_value(value, variables):
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{(\w+)\}", value)
        if match:
            var_name = match.group(1)
            if var_name not in variables:
                raise ValueError(f"Змінна {var_name} не знайдена")
            return variables[var_name]
    return value


def replace_variables_in_text(text, variables):
    def replacer(match):
        var_name = match.group(1)
        return str(variables.get(var_name, ""))
    return re.sub(r"\$\{(\w+)\}", replacer, text)


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

    raise ValueError(f"Невідомий оператор умови: {op}")


def execute_steps(steps, variables):
    for step in steps:
        step_type = step["type"]

        if step_type == "print":
            message = replace_variables_in_text(step["message"], variables)
            print(message)

        elif step_type == "set":
            variables[step["var"]] = step["value"]

        elif step_type == "add":
            a = get_value(step["a"], variables)
            b = get_value(step["b"], variables)
            variables[step["var"]] = a + b

        elif step_type == "multiply":
            a = get_value(step["a"], variables)
            b = get_value(step["b"], variables)
            variables[step["var"]] = a * b

        elif step_type == "if":
            result = check_condition(step["condition"], variables)
            if result:
                execute_steps(step["then"], variables)
            else:
                if "else" in step:
                    execute_steps(step["else"], variables)

        elif step_type == "summary":
            print("Підсумок:")
            for field in step["fields"]:
                print(f"{field} = {variables.get(field)}")

        else:
            raise ValueError(f"Невідомий тип кроку: {step_type}")


def main():
    try:
        config = load_config("config2.json")
        validate_config(config)

        variables = {}
        execute_steps(config["workflow"]["steps"], variables)

    except Exception as error:
        print("Помилка:", error)


if __name__ == "__main__":
    main()