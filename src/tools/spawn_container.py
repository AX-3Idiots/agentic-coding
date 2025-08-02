import docker
import os
from dotenv import load_dotenv
from docker.errors import ImageNotFound, NotFound
from ..constants.aws_model import AWSModel
from ..prompts.se_agent_prompts import se_agent_prompts_v1
import json

load_dotenv()

TIME_OUT = "10m"

client = docker.from_env()
image = None
try:
    image = client.images.get("se-agent:latest")
    print("Image already exists")
except ImageNotFound:
    print("Image not found, building...")    
    image, build_logs = client.images.build(path="docker", tag="se-agent:latest")
    print(f"Image built successfully::: {build_logs}")

def spawn_containers(git_url:str, jobs: list[str]) -> list[str]:
    """
    Spawn a container for each job.
    The container will implement the job using the claude-code.

    Args:
        git_url (str): The URL of the repository to clone.
        jobs (list[str]): A list of jobs to spawn.

    Returns:
        list[str]: A list of container IDs.
    """
    container_ids = []
    for job in jobs:
        container = client.containers.run(
            image,            
            command=job, 
            detach=True,
            environment={
                "GIT_URL": git_url,
                "AWS_REGION": os.environ["AWS_DEFAULT_REGION"],
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "ANTHROPIC_MODEL": AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
                "SYSTEM_PROMPT": se_agent_prompts_v1.prompt.template,
                "USER_INPUT": job,
                "TIME_OUT": TIME_OUT
            },
        )
        container_ids.append(container.id)
    return container_ids

def is_container_running(container_ids: list[str]) -> bool:
    """
    Check the status of the containers.

    Args:
        container_ids (list[str]): A list of container IDs.

    Returns:
        bool: True if any container is running, False otherwise.
    """
    if not container_ids:
        return False
        
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            if container.status == "running":
                return True
        except NotFound:
            # Container might have been removed already
            continue
    return False

def get_container_results(container_ids: list[str]) -> list[dict]:
    """
    Get the logs of the exited containers, parse the results, and remove them.

    Args:
        container_ids (list[str]): A list of exited container IDs.

    Returns:
        list[dict]: A list of dictionaries, each containing code and cost.
    """
    results = []
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            
            # Wait for the container to finish, with a timeout
            container.wait(timeout=660) # Slightly more than the internal timeout

            # Get logs
            logs = container.logs().decode('utf-8').strip().split('\n')
            
            # The last line should be our JSON result
            last_line = logs[-1] if logs else ''
            
            result_data = {}
            try:
                # Parse the JSON from the last line
                result_data = json.loads(last_line)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from logs of container {container_id}")
                print(f"Full logs for {container_id}:\n{logs}")
                result_data = {'code': None, 'cost_usd': None, 'error': 'Failed to parse result.'}

            results.append({
                'container_id': container_id,
                'code': result_data.get('code'),
                'cost_usd': result_data.get('cost_usd'),
                'error': result_data.get('error')
            })

        except NotFound:
            print(f"Warning: Container {container_id} not found. It might have been removed already.")
            results.append({
                'container_id': container_id,
                'code': None,
                'cost_usd': None,
                'error': 'Container not found.'
            })
        except Exception as e:
            print(f"An error occurred while processing container {container_id}: {e}")
            results.append({
                'container_id': container_id,
                'code': None,
                'cost_usd': None,
                'error': str(e)
            })

    return results

def remove_containers(container_ids: list[str]) -> None:
    """
    Remove the containers.
    """
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            container.remove()
        except NotFound:
            continue