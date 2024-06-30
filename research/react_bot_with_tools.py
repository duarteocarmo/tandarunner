# Imports
import json
from collections.abc import Callable
from typing import Annotated as A
from typing import Literal as L

import openai
import requests
from annotated_docs.json_schema import as_json_schema

openai_client: openai.OpenAI = openai.OpenAI(
    api_key="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"
)


class StopException(Exception):
    """
    Stop Execution by raising this exception (Signal that the task is Finished).
    """


def finish(answer: A[str, "Answer to the user's question."]) -> None:
    """Answer the user's question, and finish the conversation."""
    raise StopException(answer)


def get_current_location() -> str:
    """Get the current location of the user."""
    return json.dumps(
        requests.get("http://ip-api.com/json?fields=lat,lon").json()
    )


def get_current_weather(
    latitude: float,
    longitude: float,
    temperature_unit: L["celsius", "fahrenheit"],
) -> str:
    """Get the current weather in a given location."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "temperature_unit": temperature_unit,
            "current_weather": True,
        },
    )
    return json.dumps(resp.json())


def calculate(
    formula: A[
        str, "Numerical expression to compute the result of, in Python syntax."
    ],
) -> str:
    """Calculate the result of a given formula."""
    return str(eval(formula))


# All functions that can be called by the LLM Agent
name_to_function_map: dict[str, Callable] = {
    get_current_location.__name__: get_current_location,
    get_current_weather.__name__: get_current_weather,
    calculate.__name__: calculate,
    finish.__name__: finish,
}

# JSON Schemas for all functions
function_schemas = [
    {"function": as_json_schema(func), "type": "function"}
    for func in name_to_function_map.values()
]

# Print the JSON Schemas
for schema in function_schemas:
    print(json.dumps(schema, indent=2))


QUESTION = """
What's the current weather for my location? Give me the temperature in degrees Celsius and the wind speed in knots."
""".strip()

INSTRUCTION = """
You are a helpful assistant who can answer multistep questions by sequentially calling functions. 
Follow a pattern of THOUGHT (reason step-by-step about which function to call next), ACTION (call a function to as a next step towards the final answer), OBSERVATION (output of the function).
Reason step by step which actions to take to get to the answer. Only call functions with arguments coming verbatim from the user or the output of other functions.
""".strip()


def run(messages: list[dict]) -> list[dict]:
    """
    Run the ReAct loop with OpenAI Function Calling.
    """
    # Run in loop
    max_iterations = 20
    for i in range(max_iterations):
        # Send list of messages to get next response
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            tools=function_schemas,
            tool_choice="auto",
        )
        response_message = response.choices[0].message
        messages.append(
            response_message
        )  # Extend conversation with assistant's reply
        # Check if GPT wanted to call a function
        tool_calls = response_message.tool_calls
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                # Validate function name
                if function_name not in name_to_function_map:
                    print(f"Invalid function name: {function_name}")
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": f"Invalid function name: {function_name!r}",
                        }
                    )
                    continue
                # Get the function to call
                function_to_call: Callable = name_to_function_map[
                    function_name
                ]
                # Try getting the function arguments
                try:
                    function_args_dict = json.loads(
                        tool_call.function.arguments
                    )
                except json.JSONDecodeError as exc:
                    # JSON decoding failed
                    print(f"Error decoding function arguments: {exc}")
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": f"Error decoding function call `{function_name}` arguments {tool_call.function.arguments!r}! Error: {exc!s}",
                        }
                    )
                    continue
                # Call the selected function with generated arguments
                try:
                    print(
                        f"Calling function {function_name} with args: {json.dumps(function_args_dict)}"
                    )
                    function_response = function_to_call(**function_args_dict)
                    # Extend conversation with function response
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )
                except StopException as exc:
                    # Agent wants to stop the conversation (Expected)
                    print(f"Finish task with message: '{exc!s}'")
                    return messages
                except Exception as exc:
                    # Unexpected error calling function
                    print(
                        f"Error calling function `{function_name}`: {type(exc).__name__}: {exc!s}"
                    )
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": f"Error calling function `{function_name}`: {type(exc).__name__}: {exc!s}!",
                        }
                    )
                    continue
    return messages


messages = [
    {"role": "system", "content": INSTRUCTION},
    {
        "role": "user",
        "content": QUESTION,
    },
]
messages = run(messages)


for message in messages:
    if not isinstance(message, dict):
        message = message.model_dump()  # Pydantic model
    print(json.dumps(message, indent=2))
