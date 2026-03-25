import json


ALLOWED_ENVS = {"dev", "test", "prod"}
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}
ALLOWED_STEP_TYPES = {"print", "set", "calc", "if", "summary"}
ALLOWED_OPERATIONS = {"add", "sub", "mul", "div"}


def load_config(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict) -> None:
    # Перевірка обов'язкових розділів
    required_sections = ["app", "server", "features", "workflow"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Відсутній обов'язковий розділ: {section}")

    # app
    app = config["app"]
    if not isinstance(app.get("name"), str):
        raise TypeError("app.name має бути рядком")
    if not isinstance(app.get("version"), str):
        raise TypeError("app.version має бути рядком")
    if app.get("env") not in ALLOWED_ENVS:
        raise ValueError("app.env має бути одним із: dev, test, prod")

    # server
    server = config["server"]
    if not isinstance(server.get("host"), str):
        raise TypeError("server.host має бути рядком")
    if not isinstance(server.get("port"), int):
        raise TypeError("server.port має бути цілим числом")
    if not (1 <= server["port"] <= 65535):
        raise ValueError("server.port має бути в межах 1..65535")
    if server.get("logLevel") not in ALLOWED_LOG_LEVELS:
        raise ValueError("server.logLevel має бути одним із: debug, info, warning, error")

    # features
    features = config["features"]
    if not isinstance(features.get("enableCache"), bool):
        raise TypeError("features.enableCache має бути bool")
    if not isinstance(features.get("enableMetrics"), bool):
        raise TypeError("features.enableMetrics має бути bool")
    if not isinstance(features.get("experimental"), list):
        raise TypeError("features.experimental має бути списком")
    for item in features["experimental"]:
        if not isinstance(item, str):
            raise TypeError("Усі елементи features.experimental мають бути рядками")

    # workflow
    workflow = config["workflow"]
    if "steps" not in workflow:
        raise ValueError("Відсутній workflow.steps")
    if not isinstance(workflow["steps"], list):
        raise TypeError("workflow.steps має бути списком")
    if len(workflow["steps"]) < 8:
        raise ValueError("У workflow.steps має бути мінімум 8 кроків")

    # Перевірка кроків
    for i, step in enumerate(workflow["steps"], start=1):
        if not isinstance(step, dict):
            raise TypeError(f"Крок {i} має бути об'єктом")
        if "type" not in step:
            raise ValueError(f"Крок {i} не містить поле 'type'")
        if step["type"] not in ALLOWED_STEP_TYPES:
            raise ValueError(f"Крок {i}: невідомий тип '{step['type']}'")

        step_type = step["type"]

        if step_type == "print":
            if "message" not in step or not isinstance(step["message"], str):
                raise TypeError(f"Крок {i}: print має містити рядок 'message'")

        elif step_type == "set":
            if "var" not in step or not isinstance(step["var"], str):
                raise TypeError(f"Крок {i}: set має містити рядок 'var'")
            if "value" not in step:
                raise ValueError(f"Крок {i}: set має містити поле 'value'")

        elif step_type == "calc":
            if step.get("operation") not in ALLOWED_OPERATIONS:
                raise ValueError(f"Крок {i}: неприпустима операція")
            if not isinstance(step.get("args"), list) or len(step["args"]) != 2:
                raise TypeError(f"Крок {i}: calc.args має бути списком із 2 елементів")
            if "result" not in step or not isinstance(step["result"], str):
                raise TypeError(f"Крок {i}: calc має містити рядок 'result'")

        elif step_type == "if":
            condition = step.get("condition")
            if not isinstance(condition, dict):
                raise TypeError(f"Крок {i}: if.condition має бути об'єктом")
            for key in ["left", "op", "right"]:
                if key not in condition:
                    raise ValueError(f"Крок {i}: у condition відсутнє поле '{key}'")
            if condition["op"] not in [">", "<", ">=", "<=", "==", "!="]:
                raise ValueError(f"Крок {i}: невірний оператор умови")
            if "then" not in step or not isinstance(step["then"], list):
                raise TypeError(f"Крок {i}: if.then має бути списком")
            if "else" in step and not isinstance(step["else"], list):
                raise TypeError(f"Крок {i}: if.else має бути списком")

        elif step_type == "summary":
            if "vars" not in step or not isinstance(step["vars"], list):
                raise TypeError(f"Крок {i}: summary має містити список 'vars'")


def resolve_value(value, variables: dict):
    if isinstance(value, str) and value.startswith("$"):
        var_name = value[1:]
        if var_name not in variables:
            raise ValueError(f"Змінна '{var_name}' не визначена")
        return variables[var_name]
    return value


def format_message(message: str, variables: dict) -> str:
    return message.format(**variables)


def calculate(operation: str, left, right):
    if operation == "add":
        return left + right
    elif operation == "sub":
        return left - right
    elif operation == "mul":
        return left * right
    elif operation == "div":
        if right == 0:
            raise ZeroDivisionError("Ділення на нуль")
        return left / right
    else:
        raise ValueError(f"Невідома операція: {operation}")


def check_condition(condition: dict, variables: dict) -> bool:
    left = resolve_value(condition["left"], variables)
    right = resolve_value(condition["right"], variables)
    op = condition["op"]

    if op == ">":
        return left > right
    elif op == "<":
        return left < right
    elif op == ">=":
        return left >= right
    elif op == "<=":
        return left <= right
    elif op == "==":
        return left == right
    elif op == "!=":
        return left != right
    else:
        raise ValueError(f"Невідомий оператор: {op}")


def execute_steps(steps: list, variables: dict) -> None:
    for step in steps:
        step_type = step["type"]

        if step_type == "print":
            print(format_message(step["message"], variables))

        elif step_type == "set":
            variables[step["var"]] = resolve_value(step["value"], variables)

        elif step_type == "calc":
            left = resolve_value(step["args"][0], variables)
            right = resolve_value(step["args"][1], variables)
            result = calculate(step["operation"], left, right)
            variables[step["result"]] = result

        elif step_type == "if":
            if check_condition(step["condition"], variables):
                execute_steps(step["then"], variables)
            else:
                execute_steps(step.get("else", []), variables)

        elif step_type == "summary":
            print("----- ПІДСУМОК -----")
            for var_name in step["vars"]:
                value = variables.get(var_name, "невизначено")
                print(f"{var_name} = {value}")


def main():
    try:
        config = load_config("config1.json")
        validate_config(config)

        variables = {}
        execute_steps(config["workflow"]["steps"], variables)

    except Exception as error:
        print(f"Помилка: {error}")


if __name__ == "__main__":
    main()