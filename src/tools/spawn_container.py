import docker
import os
from dotenv import load_dotenv
from docker.errors import ImageNotFound, NotFound, DockerException
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

TIME_OUT = "1000"

# Docker client and image will be initialized lazily
_client = None
_image = None

def _get_docker_client():
    """
    Get Docker client with proper error handling for Rancher Desktop and other Docker environments.
    """
    global _client
    if _client is None:
        try:
            # Try different Docker socket paths for various environments
            docker_socket_paths = [
                None,  # Default from environment
                "unix:///var/run/docker.sock",  # Standard Docker Desktop
                "unix://~/.docker/run/docker.sock",  # Rancher Desktop (newer versions)
                "unix://~/.rd/docker.sock",  # Rancher Desktop (older versions)
            ]
            
            for socket_path in docker_socket_paths:
                try:
                    if socket_path is None:
                        _client = docker.from_env()
                    else:
                        # Expand user path for socket
                        if socket_path.startswith("unix://~/"):
                            expanded_path = socket_path.replace("~/", os.path.expanduser("~/"))
                            _client = docker.DockerClient(base_url=expanded_path)
                        else:
                            _client = docker.DockerClient(base_url=socket_path)
                    
                    # Test the connection
                    _client.ping()
                    logger.info(f"Successfully connected to Docker using socket: {socket_path or 'default'}")
                    break
                    
                except (DockerException, Exception) as e:
                    logger.debug(f"Failed to connect using socket {socket_path}: {e}")
                    _client = None
                    continue
            
            if _client is None:
                raise DockerException(
                    "Could not connect to Docker daemon. Please ensure:\n"
                    "1. Rancher Desktop is running\n"
                    "2. Docker context is set correctly\n"
                    "3. Docker socket is accessible\n"
                    "Try running: docker context ls && docker context use rancher-desktop"
                )
                
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise DockerException(f"Docker initialization failed: {e}")
    
    return _client

def _get_or_build_image():
    """
    Get or build the SE agent Docker image.
    """
    global _image
    if _image is None:
        client = _get_docker_client()
        
        # Construct the absolute path to the docker build context directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        src_path = os.path.join(script_dir, "..")
        
        try:
            _image = client.images.get("se-agent:latest")
            logger.info("Image 'se-agent:latest' already exists")
        except ImageNotFound:
            logger.info("Image not found, building...")    
            _image, build_logs = client.images.build(
                path=src_path, 
                dockerfile="docker/Dockerfile", 
                tag="se-agent:latest"
            )
            logger.info(f"Image built successfully")
    
    return _image

def _spawn_containers(git_url:str, branch_names:dict[str, str], jobs: list[dict]) -> list[str]:
    """
    Spawn a container for each job.
    The container will implement the job using the claude-code.

    Args:
        git_url (str): The URL of the repository to clone.
        branch_names (dict[str, str]): A dictionary of branch names for frontend and backend.
        jobs (list[dict]): A list of jobs to spawn.

    Returns:
        list[str]: A list of container IDs.
    """
    client = _get_docker_client()
    image = _get_or_build_image()
    
    container_ids = []
    for job in jobs:
        volume_name = f"se-agent-volume-{uuid.uuid4()}"
        user_input = json.dumps(job)
        system_prompt = se_agent_prompts_v1.prompt.invoke({
            "language": "Javascript", 
            "framework": "React", 
            "library": "Any",
            "fe_branch_name": branch_names.get("fe_branch_name"),
            "be_branch_name": branch_names.get("be_branch_name"),
            "user_story": user_input
        }).messages[0].content
        
        volume = client.volumes.create(name=volume_name)
        container = client.containers.run(
            image,            
            mem_limit="8g",
            cpu_quota=200000,
            cpu_period=100000,
            network_mode="host",
            detach=True,
            environment={
                "GIT_URL": git_url,
                "AWS_REGION": os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2"),
                "CLAUDE_CODE_USE_BEDROCK": 1,
                "ANTHROPIC_MODEL": AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION.value,
                "SYSTEM_PROMPT": system_prompt,
                "USER_INPUT": user_input,
                "TIME_OUT": TIME_OUT,
                "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", ""),
                "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
                "GITHUB_TOKEN": os.environ.get("GH_APP_TOKEN"),
                "JOB_NAME": job.get("group_name"),
                "INSTALLATION_ID": os.environ.get("INSTALLATION_ID"),
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": 9136,
                "MAX_THINKING_TOKENS": 1024
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
    
    client = _get_docker_client()
        
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
    client = _get_docker_client()
    results = []
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            
            # Wait for the container to finish, with a timeout
            container.wait(timeout=1060) # Slightly more than the internal timeout

            # Get logs
            logs = container.logs().decode('utf-8').strip().split('\n')
            logger.info(f"results for {container_id}:\n{logs}")
            # The last line should be our JSON result
            last_line = logs[-1] if logs else ''            
            result_data = {}
            try:
                # Parse the JSON from the last line
                result_data = json.loads(last_line)
            except json.JSONDecodeError:
                logger.warning(f"Warning: Could not decode JSON from logs of container {container_id}")
                logger.warning(f"Full logs for {container_id}:\n{logs}")
                result_data = {'code': None, 'cost_usd': None, 'error': f"Failed to parse result. Full logs: {logs}"}

            results.append({
                'container_id': container_id,
                'code': result_data.get('code'),
                'cost_usd': result_data.get('cost_usd'),
                'error': result_data.get('error'),
                'log': logs[:-1]
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
    client = _get_docker_client()
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            logging.info(f"Removing container {container.name} ({container.id})")

            # Get volume names from the container's attributes before removing it
            mounts = container.attrs.get("Mounts", [])
            volume_names = []
            for mount in mounts:
                if mount.get("Type") == "volume":
                    volume_name = mount.get("Name")
                    if volume_name:
                        volume_names.append(volume_name)

            # Stop and remove the container, and its anonymous volumes
            container.remove(force=True, v=True)
            logging.info(f"Successfully removed container {container.name}")

            # Now that the container is gone, remove its named volumes
            if volume_names:
                logging.info(f"Removing named volumes for {container.name}: {volume_names}")
            for volume_name in volume_names:
                try:
                    volume = client.volumes.get(volume_name)
                    volume.remove(force=True)
                    logging.info(f"Successfully removed volume {volume_name}")
                except NotFound:
                    logging.warning(f"Volume {volume_name} not found, skipping.")
                    continue
                except Exception as e:
                    logging.error(f"Error removing volume {volume_name}: {e}")
        except NotFound:
            logging.warning(f"Container {container_id} not found, skipping.")
            continue
        except Exception as e:
            logging.error(f"Error removing container {container_id}: {e}")

def spawn_engineers(git_url: str, branch_names: dict[str, str], jobs: list[dict]) -> list[dict]:
    """
    Spawn a container for each job and clean up the containers after the job is done.
    The container will implement the job using the claude-code.

    Args:
        git_url (str): The URL of the repository to clone.
        branch_names (dict[str, str]): A dictionary of branch names for frontend and backend.
        jobs (list[dict]): A list of jobs to spawn.

    Returns:
        list[dict]: A list of dictionaries, each containing code and cost.
    """
    container_ids = []
    try:
        container_ids = _spawn_containers(git_url, branch_names, jobs)
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
    
