import subprocess
import logging
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ShellCommandInput(BaseModel):
    """Input for the execute_shell_command tool."""
    command: str = Field(description="The shell command to be executed in the interactive terminal.")

class ExecuteShellCommandTool(BaseTool):
    """
    A tool to execute shell commands.
    It is crucial for tasks requiring interaction with the operating system's shell,
    such as file manipulation, git operations, or running scripts.
    """
    name: str = "execute_shell_command"
    description: str = (
        "Executes a shell command and returns its standard output, standard error, and exit code. "
        "Use this for all shell-based operations like 'ls', 'mkdir', 'cd', 'git', 'curl', etc. "
        "IMPORTANT: The 'cd' command must be handled carefully, as each command runs in a new shell. "
        "To maintain state across commands, chain them with '&&', e.g., 'cd my_dir && ls'."
    )
    args_schema: Type[BaseModel] = ShellCommandInput

    def _run(self, command: str) -> str:
        """Use the tool."""
        logging.info(f"Executing command: {command}")

        try:
            # shell=True를 사용하여 파이프(|)나 리디렉션(>) 같은 쉘 기능을 사용할 수 있도록 합니다.
            # 이 기능은 프롬프트의 curl | grep | cut 과 같은 복잡한 명령어 실행에 필수적입니다.
            # capture_output=True는 stdout과 stderr를 캡처하기 위함입니다.
            # text=True는 결과를 문자열로 디코딩합니다.
            # timeout을 설정하여 무한정 실행되는 것을 방지합니다.
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=False,  # check=False로 설정하여 0이 아닌 종료 코드에서도 예외를 발생시키지 않도록 합니다.
                timeout=300,  # 5분 타임아웃
                env=os.environ.copy()
            )

            # AI 에이전트가 결과를 명확히 이해할 수 있도록 포맷팅합니다.
            output = f"Exit Code: {process.returncode}\n"

            if process.stdout:
                output += f"--- STDOUT ---\n{process.stdout.strip()}\n"
            else:
                output += "--- STDOUT ---\n[No output]\n"

            if process.stderr:
                output += f"--- STDERR ---\n{process.stderr.strip()}\n"
            else:
                output += "--- STDERR ---\n[No output]\n"

            logging.info(f"Command executed. Exit Code: {process.returncode}")
            return output

        except subprocess.TimeoutExpired:
            logging.error(f"Command '{command}' timed out.")
            return "Error: Command timed out after 300 seconds."
        except Exception as e:
            logging.error(f"An unexpected error occurred while executing command '{command}': {e}")
            return f"An unexpected error occurred: {str(e)}"

# 사용 예시 (LangChain 에이전트에 이 도구를 전달할 수 있습니다)
cli_tool = ExecuteShellCommandTool()

# 아래와 같이 직접 테스트해볼 수도 있습니다.
if __name__ == '__main__':
    # 프롬프트에 있는 명령어 예시 테스트
    # 1. 디렉토리 생성 및 이동
    print("--- Testing mkdir and ls ---")
    result1 = cli_tool.run("mkdir test_project && cd test_project && ls -la")
    print(result1)

    # 2. git 초기화
    print("\n--- Testing git init ---")
    result2 = cli_tool.run("cd test_project && git init")
    print(result2)

    # 3. 정리
    print("\n--- Cleaning up ---")
    result3 = cli_tool.run("rm -rf test_project")
    print(result3)
