# SYNORPSE

An advanced modular AI assistant framework focused on **agentic workflows, automation, multimodal interaction, proactive behavior, and real-time task execution**.

SYNORPSE combines conversational AI, system automation, vision capabilities, background task orchestration, proactive suggestions, and extensible tooling into a single intelligent assistant architecture.

---

# Features

## Agentic AI Core

* Autonomous and supervised agent modes
* Task planning and execution pipeline
* Priority-based task management
* Background task scheduling
* Context-aware decision making
* Persistent conversational memory
* Modular capability registry

## Conversational Intelligence

* Groq-powered chatbot integration
* Multi-key API rotation for reliability
* Context-aware conversations
* Persistent chat history
* Intent routing and command chaining
* Dynamic capability-aware prompting

## Automation System

* File and system automation
* App launching and control
* Background workflow execution
* Task dependency handling
* Automation logging and monitoring

## Real-Time Search & Knowledge

* Real-time web search integration
* Search caching
* Structured result handling
* Search database initialization

## Vision & Image Capabilities

* Image generation support
* Advanced vision modules
* OCR and image-processing foundations
* Local image generation pipeline

## System Awareness

* State persistence
* Goal persistence
* Audit logging
* Security and input validation
* Performance monitoring
* System-level awareness modules

## Frontend Components

* Interactive sphere UI
* Frontend widget system
* Lightweight visual interface

---

# Project Architecture

```text
SYNORPSE/
│
├── BackEnd/
│   ├── AgenticCore.py
│   ├── ChatBot.py
│   ├── Automation.py
│   ├── CommandHandlers.py
│   ├── IntentRouter.py
│   ├── TaskExecutor.py
│   ├── BackgroundTaskManager.py
│   ├── CapabilityRegistry.py
│   └── ...
│
├── Frontend/
│   ├── sphere.html
│   ├── sphere.css
│   ├── sphere.js
│   └── sphere_widget.py
│
├── AdvancedVision/
├── Data/
├── logs/
├── state/
├── tools/
│
├── mainagentic.py
├── config.yaml
└── README.md
```

---

# Core Components

## AgenticCore

The central orchestration engine responsible for:

* Task decomposition
* Agent execution modes
* Task prioritization
* State tracking
* Autonomous behavior handling

### Supported Modes

| Mode       | Description                                |
| ---------- | ------------------------------------------ |
| Reactive   | Responds directly to user requests         |
| Proactive  | Suggests actions based on patterns/context |
| Autonomous | Executes independent workflows             |
| Supervised | Requires user oversight for major actions  |

---

## ChatBot System

Handles:

* Conversational interactions
* Context memory
* Groq API integration
* Multi-key rotation
* Retry handling
* Persistent storage

---

## Intent Router & Command Chain

The system supports structured command routing:

* Intent detection
* Capability mapping
* Chain execution
* Multi-step workflow routing

---

## Background Task Manager

Enables:

* Concurrent task execution
* Background workflows
* Scheduled processing
* Task isolation
* Retry mechanisms

---

# Technologies Used

## AI & ML

* Groq API
* Python
* Local image generation pipelines

## Backend

* asyncio
* PostgreSQL
* YAML configuration
* Logging infrastructure

## Frontend

* HTML
* CSS
* JavaScript
* Python frontend widgets

## Vision & Processing

* OCR-ready architecture
* Vision processing modules
* Image generation support

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/yourusername/synorpse.git
cd synorpse
```

---

## 2. Create a Virtual Environment

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file:

```env
GroqAPIKey=YOUR_API_KEY
DB_NAME=synorpse_chat
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
Assistantname=Synorpse
Username=User
```

---

## 5. Configure `config.yaml`

Adjust:

* Agent modes
* Logging behavior
* Image generation settings
* Automation settings
* Search settings

---

# Running the Project

```bash
python mainagentic.py
```

---

# Logging & Monitoring

Logs are stored in:

```text
logs/
├── audit.log
├── errors.log
├── performance.log
└── synorpse.log
```

The framework includes:

* Audit tracking
* Performance timing
* Error monitoring
* Execution tracing

---

# Security Features

* Input validation
* Rate limiting
* Audit logging
* Safe task execution
* Controlled automation flows

---

# Future Goals

* Full multimodal interaction
* Voice assistant support
* Advanced autonomous agents
* Better memory systems
* Expanded vision capabilities
* Distributed task execution
* Plugin ecosystem
* Smart wearable integration

---

# Example Use Cases

## Personal AI Assistant

* Smart automation
* Scheduling
* Conversational workflows
* Task management

## Research Assistant

* Real-time search
* Knowledge aggregation
* Summarization pipelines

## Automation Engine

* Background workflows
* File handling
* App launching
* Multi-step automation

## Experimental Agentic AI Platform

* Autonomous planning
* Task decomposition
* AI workflow experimentation

---

# Why SYNORPSE?

SYNORPSE is designed as more than a chatbot.

It is a modular experimental framework for building:

* agentic systems,
* autonomous workflows,
* intelligent assistants,
* multimodal AI applications,
* and proactive AI environments.

The architecture emphasizes extensibility, modularity, and experimentation with next-generation AI assistant behavior.

---

# Author

Developed by Sai Rachit Singh.

