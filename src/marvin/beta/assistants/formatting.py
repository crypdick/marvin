import inspect
import json
import tempfile
from datetime import datetime

import openai
from openai.types.beta.threads import Message
from openai.types.beta.threads.runs.run_step import RunStep
from partialjson import JSONParser
from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel

json_parser = JSONParser()


def format_step(step: RunStep) -> list[Panel]:
    # Timestamp formatting
    timestamp = datetime.fromtimestamp(step.created_at).strftime("%l:%M:%S %p")

    # default content
    content = (
        f"Assistant is performing an action: {step.type} - Status:" f" {step.status}"
    )

    panels = []

    # attempt to customize content
    if step.type == "tool_calls":
        for tool_call in step.step_details.tool_calls:
            if tool_call.type == "code_interpreter":
                if tool_call.code_interpreter.outputs:
                    footer = inspect.cleandoc(
                        """
                        Result:
                        
                        ```python
                        {result}
                        ```
                        """
                    ).format(result=tool_call.code_interpreter.outputs[0].logs)
                else:
                    footer = ""
                content = inspect.cleandoc(
                    """
                    Assistant is running the code interpreter...
                    
                    ```python
                    {input}
                    ```
                    
                    {footer}
                    """
                ).format(input=tool_call.code_interpreter.input, footer=footer)
            elif tool_call.type == "function":
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    try:
                        args = json_parser.parse(tool_call.function.arguments)
                    except Exception:
                        args = tool_call.function.arguments

                if tool_call.function.output:
                    footer = inspect.cleandoc(
                        """
                        Result:
                        
                        ```python
                        {result}
                        ```
                        """
                    ).format(result=tool_call.function.output)
                else:
                    footer = ""

                content = inspect.cleandoc(
                    """
                    Assistant is using the `{function}` tool with arguments:
                    
                    ```python
                    {args}
                    ```
                    
                    {footer}
                    """
                ).format(function=tool_call.function.name, args=args, footer=footer)

            # Create the panel for the run step status
            panels.append(
                Panel(
                    Markdown(inspect.cleandoc(content)),
                    title="System",
                    subtitle=f"[italic]{timestamp}[/]",
                    title_align="left",
                    subtitle_align="right",
                    border_style="gray74",
                    box=box.ROUNDED,
                    width=100,
                    expand=True,
                    padding=(1, 2),
                )
            )

    elif step.type == "message_creation":
        pass

    return Group(*panels)


def pprint_run_step(step: RunStep):
    """
    Formats and prints a run step with status information.

    Args:
        run_step: A RunStep object containing the details of the run step.
    """
    panel = format_step(step)

    if not panel:
        return

    console = Console()
    console.print(panel)


def download_temp_file(file_id: str, suffix: str = None):
    """
    Downloads a file from OpenAI's servers and saves it to a temporary file.

    Args:
        file_id: The ID of the file to be downloaded.
        suffix: The file extension to be used for the temporary file.

    Returns:
        The file path of the downloaded temporary file.
    """

    client = openai.Client()
    # file_info = client.files.retrieve(file_id)
    file_content_response = client.files.with_raw_response.retrieve_content(file_id)

    # Create a temporary file with a context manager to ensure it's cleaned up
    # properly
    with tempfile.NamedTemporaryFile(
        delete=False, mode="wb", suffix=f"{suffix}"
    ) as temp_file:
        temp_file.write(file_content_response.content)
        temp_file_path = temp_file.name  # Save the path of the temp file

    return temp_file_path


def format_message(message: Message) -> Panel:
    role_colors = {
        "user": "green",
        "assistant": "blue",
    }

    color = role_colors.get(message.role, "red")
    timestamp = (
        datetime.fromtimestamp(message.created_at).strftime("%I:%M:%S %p").lstrip("0")
    )

    content = ""
    for item in message.content:
        if item.type == "text":
            content += item.text.value + "\n\n"
        elif item.type == "image_file":
            # Use the download_temp_file function to download the file and get
            # the local path
            local_file_path = download_temp_file(item.image_file.file_id, suffix=".png")
            # Add a clickable hyperlink to the content
            file_url = f"file://{local_file_path}"
            content += (
                "[bold]Attachment[/bold]:"
                f" [blue][link={file_url}]{local_file_path}[/link][/blue]\n\n"
            )

    for file_id in message.file_ids:
        content += f"Attached file: {file_id}\n"

    # Create the panel for the message
    panel = Panel(
        Markdown(inspect.cleandoc(content)),
        title=f"[bold]{message.role.capitalize()}[/]",
        subtitle=f"[italic]{timestamp}[/]",
        title_align="left",
        subtitle_align="right",
        border_style=color,
        box=box.ROUNDED,
        # highlight=True,
        width=100,  # Fixed width for all panels
        expand=True,  # Panels always expand to the width of the console
        padding=(1, 2),
    )
    return panel


def pprint_message(message: Message):
    """
    Pretty-prints a single message using the rich library, highlighting the
    speaker's role, the message text, any available images, and the message
    timestamp in a panel format.

    Args:
        message (Message): A message object
    """
    console = Console()
    panel = format_message(message)
    console.print(panel)


def pprint_messages(messages: list[Message]):
    """
    Iterates over a list of messages and pretty-prints each one.

    Messages are pretty-printed using the rich library, highlighting the
    speaker's role, the message text, any available images, and the message
    timestamp in a panel format.

    Args:
        messages (list[Message]): A list of Message objects to be
            printed.
    """
    for message in messages:
        pprint_message(message)


def format_run(run) -> list[Panel]:
    """
    Formats a run, which is an object that has both `.messages` and `.steps` attributes, each of which is a list of Messages and RunSteps.
    """

    sorted_objects = sorted(
        [(format_message(m), m.created_at) for m in run.messages]
        + [(format_step(s), s.created_at) for s in run.steps],
        key=lambda x: x[1],
    )
    return [x[0] for x in sorted_objects if x[0] is not None]


def pprint_run(run):
    """
    Pretty-prints a run, which is an object that has both `.messages` and `.steps` attributes, each of which is a list of Messages and RunSteps.
    Args:
        run: A Run object
    """
    console = Console()
    panels = format_run(run)
    console.print(Group(*panels))
