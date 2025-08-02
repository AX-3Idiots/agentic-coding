FROM node:18-slim
RUN apt-get update && apt-get install -y git
RUN npm install -g @anthropic-ai/claude-code
# Create the .claude directory and the settings.json file
RUN mkdir -p /root/.claude && \
    echo '{ \
      "permissions": { \
        "allow": [ "Read(*)", "Edit(*)", "Write(*)" ] \
      }, \
      "defaultMode": "acceptEdits" \
    }' > /root/.claude/settings.json
WORKDIR /workspace
COPY ./src/scripts/se_agent.sh /usr/local/bin/se_agent.sh
RUN chmod +x /usr/local/bin/se_agent.sh
ENTRYPOINT ["bash", "/usr/local/bin/se_agent.sh"]