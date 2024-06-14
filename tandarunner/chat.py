from litellm import acompletion, litellm

litellm.set_verbose = False


async def generate_response_to(list_of_messages: list[dict]):
    return await acompletion(
        model="gpt-3.5-turbo",
        messages=list_of_messages,
        stream=True,
    )
