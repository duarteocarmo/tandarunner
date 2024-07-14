from litellm import acompletion, litellm

litellm.set_verbose = False


async def generate_response_to(list_of_messages: list[dict]):
    return await acompletion(
        model="gpt-3.5-turbo",
        messages=list_of_messages,
        stream=True,
    )


async def generate_insight_for(athlete):
    first_name = athlete["athlete"]["firstname"]
    return f"This is a message for {first_name}! Welcome to the chat!"
