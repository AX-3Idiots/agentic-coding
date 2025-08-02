import docker
import os
from dotenv import load_dotenv
from docker.errors import ImageNotFound
from ..constants.aws_model import AWSModel
from ..prompts.se_agent_prompts import se_agent_prompts_v1

load_dotenv()

client = docker.from_env()
image = None
try:
    image = client.images.get("se-agent:latest")
    print("Image already exists")
except ImageNotFound:
    print("Image not found, building...")    
    image, build_logs = client.images.build(path="docker", tag="se-agent:latest")
    print(f"Image built successfully::: {build_logs}")

def spawn_container(git_url:str,jobs: list[str]) -> list[str]:
    """
    Spawn a container for each job.
    The container will implement the job using the claude-code.

    Args:
        repo_url (str): The URL of the repository to clone.
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
                "CLAUDE_CODE_USE_BEDROCK": 1,
                "ANTHROPIC_MODEL": AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
                "SYSTEM_PROMPT": se_agent_prompts_v1.prompt.template,
                "USER_INPUT": job,
                "TIME_OUT": "10m"
            },
        )
        container_ids.append(container.id)
    return container_ids