# ATHENA Roadmap

Each milestone should leave the project in a working state.

## Phase 1: Foundation

- Create the project structure
- Add setup documentation
- Add health checks
- Add basic local chat

Done when ATHENA can talk to a local Ollama model from the terminal.

## Phase 2: Conversation History

- Save chats to local files
- Add simple session names
- Add basic search over past chats

Done when ATHENA can recall earlier conversation files.

## Phase 3: Personal Memory

- Add a small local memory file
- Let the user add facts manually
- Let ATHENA read those facts before answering

Done when ATHENA can remember stable facts like project names, people, and preferences.

Status: implemented with `memory/profile.md` and the `/remember` command.

## Phase 4: Document Search

- Add a documents folder
- Extract text from PDFs, Word files, and text files
- Add lightweight retrieval

Done when ATHENA can answer questions from your own documents.

## Phase 5: Internet Search

- Add search tool integration
- Add source tracking
- Summarize current information safely

Done when ATHENA can answer questions that need fresh information.

## Phase 6: Voice

- Add speech-to-text
- Add text-to-speech
- Add push-to-talk first, wake word later

Done when you can speak to ATHENA and hear the response.

## Phase 7: Coding Assistant

- Add Git helpers
- Add project file reading
- Add patch generation
- Add test execution

Done when ATHENA can help edit and verify local code.

## Phase 8: Infrastructure Assistant

- Add Docker helpers
- Add Kubernetes helpers
- Add Jenkins helpers
- Add OpenStack helpers

Done when ATHENA can inspect infrastructure safely and explain issues.

## Phase 9: Agents and Automation

- Add planned tool use
- Add approval gates
- Add scheduled checks
- Add safety logs

Done when ATHENA can perform multi-step tasks with user approval.
