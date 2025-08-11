import docker
import os
from dotenv import load_dotenv
from docker.errors import ImageNotFound, NotFound
from ..constants.aws_model import AWSModel
from ..prompts.se_agent_prompts import se_agent_prompts_v1
import json
import uuid
import time
from ..logging_config import setup_logging
import logging

load_dotenv()

setup_logging()
logger = logging.getLogger(__name__)

TIME_OUT = "600"

client = docker.from_env()
image = None

# Construct the absolute path to the docker build context directory
script_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(script_dir, "..")

try:
    image = client.images.get("se-agent:latest")
    print("Image already exists")
except ImageNotFound:
    print("Image not found, building...")    
    image, build_logs = client.images.build(path=src_path, dockerfile="docker/Dockerfile", tag="se-agent:latest")
    print(f"Image built successfully::: {build_logs}")

def _spawn_containers(git_url:str, branch_name:str, jobs: list[dict]) -> list[str]:
    """
    Spawn a container for each job.
    The container will implement the job using the claude-code.

    Args:
        git_url (str): The URL of the repository to clone.
        branch_name (str): The name of the branch to create.
        jobs (list[dict]): A list of jobs to spawn.

    Returns:
        list[str]: A list of container IDs.
    """
    container_ids = []
    for job in jobs:
        volume_name = f"se-agent-volume-{uuid.uuid4()}"
        volume = client.volumes.create(name=volume_name)
        container = client.containers.run(
            image,            
            mem_limit="4g",
            cpu_quota=200000,
            cpu_period=100000,
            network_mode="host",
            detach=True,
            environment={
                "GIT_URL": git_url,
                "AWS_REGION": os.environ["AWS_DEFAULT_REGION"],
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "ANTHROPIC_MODEL": AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION.value,
                "SYSTEM_PROMPT": se_agent_prompts_v1.prompt.messages[0].prompt.template.strip(),
                "USER_INPUT": json.dumps(job),
                "TIME_OUT": TIME_OUT,
                "AWS_ACCESS_KEY_ID": os.environ["AWS_ACCESS_KEY"],
                "AWS_SECRET_ACCESS_KEY": os.environ["AWS_SECRET_KEY"],
                "GITHUB_TOKEN": os.environ.get("GH_APP_TOKEN"),
                "BRANCH_NAME": branch_name,
                "JOB_NAME": job.get("group_name"),
            },
            volumes={volume.name: {"bind": "/app", "mode": "rw"}},
        )
        container_ids.append(container.id)
    return container_ids

def _is_container_running(container_ids: list[str]) -> bool:
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

def _get_container_results(container_ids: list[str]) -> list[dict]:
    """
    Get the logs of the exited containers and parse the results.

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
            print(f"Logs for {container_id}:\n{logs}")
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

def _remove_containers(container_ids: list[str]) -> None:
    """
    Remove the containers and their associated volumes.
    """
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            
            # Get volume names from the container's attributes before removing it
            mounts = container.attrs.get('Mounts', [])
            volume_names = []
            for mount in mounts:
                if mount.get('Type') == 'volume':
                    volume_name = mount.get('Name')
                    if volume_name:
                        volume_names.append(volume_name)

            # Stop and remove the container first to release the volume
            container.remove(force=True)

            # Now that the container is gone, remove its volumes
            for volume_name in volume_names:
                try:
                    volume = client.volumes.get(volume_name)
                    volume.remove(force=True)
                except NotFound:
                    # This can happen if the volume was manually removed or never created properly
                    continue
        except NotFound:
            # This can happen if the container was already removed
            continue

def spawn_engineers(git_url: str, branch_name: str, jobs: list[dict]) -> list[dict]:
    """
    Spawn a container for each job and clean up the containers after the job is done.
    The container will implement the job using the claude-code.

    Args:
        git_url (str): The URL of the repository to clone.
        branch_name (str): The name of the branch to create.
        jobs (list[dict]): A list of jobs to spawn.

    Returns:
        list[dict]: A list of dictionaries, each containing code and cost.
    """
    container_ids = []
    try:
        container_ids = _spawn_containers(git_url, branch_name, jobs)
        while _is_container_running(container_ids):
            print("Waiting for containers to finish...")
            time.sleep(10)
        results = _get_container_results(container_ids)
        return results
    except Exception as e:
        logger.error(f"An error occurred while spawning containers: {e}")
        return []
    finally:
        if container_ids:
            _remove_containers(container_ids)
    
