FROM node:18-slim
RUN apt-get update && apt-get install -y git jq
ENV HOME /root
RUN npm install -g @anthropic-ai/claude-code
# Create the .claude directory and the settings.json file for claude-codepermission
RUN mkdir -p /root/.claude && \
    echo '{ \
      "permissions": { \
        "allow": [ "Read(*)", "Edit(*)", "Write(*)", "Bash(npm run lint)", "Bash(npm run test:*)", "Bash(git:*)" ] \
      }, \
      "defaultMode": "acceptEdits" \
    }' > /root/.claude/settings.json
WORKDIR /workspace
COPY ./scripts/se_agent.sh /usr/local/bin/se_agent.sh
RUN chmod +x /usr/local/bin/se_agent.sh
ENTRYPOINT ["bash", "/usr/local/bin/se_agent.sh"]