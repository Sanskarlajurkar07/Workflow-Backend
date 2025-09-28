# Workflow Automation: Updated Node Documentation

This document outlines the redesigned workflow nodes that have been implemented in the workflow automation system.

## AI & Language Nodes

### AI Tools Node

The AI Tools node provides an interface to various AI language models for generating text content.

#### Features:
- Supports multiple AI providers (OpenAI, Anthropic, Google Gemini, Cohere)
- Configurable models, max tokens, and temperature
- System prompt and template customization
- Variable replacement in prompts
- **Variable name customization with insert button**

#### Configuration:
- **Provider**: Select the AI provider to use
- **Model**: Select the specific model from the chosen provider
- **Max Tokens**: Maximum tokens to generate in the response
- **Temperature**: Controls creativity level (0.0-1.0)
- **System Prompt**: Instructions for the AI model
- **Prompt Template**: Template for structuring the prompt with variables
- **Variable Name**: Name to store the result for later use in the workflow
- **Variable Insert Button**: Easy insertion of workflow variables into templates

### Spark Layer Node

The Spark Layer node handles vector embeddings for semantic operations in AI workflows.

#### Features:
- Text to embedding conversion
- Embedding similarity comparison
- Semantic search using embeddings
- **Variable name customization with insert button**

#### Configuration:
- **Mode**: Operation mode (text_to_embedding, embedding_similarity, semantic_search)
- **Provider**: Embedding provider to use
- **Model**: Specific embedding model
- **Input Format**: Single input or batch processing
- **Dimension**: Vector dimension for the embeddings
- **Variable Name**: Name to store the result for later use
- **Variable Insert Button**: Easy insertion of workflow variables

### AI Task Executor Node

The AI Task Executor node performs specific AI tasks on input data.

#### Features:
- Text summarization with adjustable length and style
- Sentiment analysis with scores and detailed analysis
- Content generation with format and tone controls
- Translation to different languages
- Text classification into categories
- **Variable name customization with insert button**

#### Configuration:
- **Task Type**: Type of AI task to execute
- **Provider**: AI provider to use
- **Model**: Specific model for the task
- **Task Config**: Task-specific configuration options
- **Variable Name**: Name to store the result for later use
- **Variable Insert Button**: Easy insertion of workflow variables into task configurations

### Chat Memory Node

The Chat Memory node stores and manages conversation history for contextual chat responses.

#### Features:
- Configurable memory types (token-based, message-based, etc.)
- Automatic token/message limiting
- Formatted context creation for AI models
- Support for different message formats
- **Variable name customization with insert button**
- **Persistent memory across workflow runs**

#### Configuration:
- **Memory Type**: Type of memory management to use
- **Memory Size**: Maximum size of the memory in tokens or messages
- **Variable Name**: Name to store the memory for later use
- **Variable Insert Button**: Easy insertion of memory content into other nodes

## Data Processing Nodes

### Data Collector Node

The Data Collector node gathers structured data from users based on defined fields.

#### Features:
- Customizable prompts and instructions
- Configurable fields with descriptions and examples
- Structured data output
- **Variable name customization with insert button**
- **Field-specific variable insertion**

#### Configuration:
- **Query**: Main question or prompt to show users
- **Prompt**: Detailed instructions for data collection
- **Fields**: Structured fields to collect (name, description, example)
- **Variable Name**: Name to store the collected data for later use
- **Variable Insert Button**: Easy insertion of workflow variables into prompts and field definitions

### Chat File Reader Node

The Chat File Reader node processes files uploaded in chat or from predefined locations.

#### Features:
- Support for various file types
- File size limits and validation
- Structured metadata extraction
- Dynamic content handling based on file type
- **Variable name customization with insert button**
- **Variable-based file path selection**

#### Configuration:
- **File Type**: Type of files to accept
- **Max File Size**: Maximum allowed file size in MB
- **Selected File**: Predefined file path to read (supports variables)
- **Variable Name**: Name to store the file data for later use
- **Variable Insert Button**: Easy insertion of file content into other nodes

### Text Processor Node

The Text Processor node performs various text manipulation operations.

#### Features:
- Text transformations (case changes, formatting)
- Pattern-based text replacement
- Regular expression pattern extraction
- Text splitting and analysis
- **Variable name customization with insert button**
- **Pattern/replacement variable support**

#### Configuration:
- **Operation**: Type of text operation to perform
- **Transform Type**: Specific transformation (for transform operation)
- **Pattern**: Pattern to find in text (supports variables)
- **Replacement**: Replacement text for pattern (supports variables)
- **Extract Pattern**: Regex pattern for extraction (supports variables)
- **Split Delimiter**: Delimiter for text splitting (supports variables)
- **Variable Name**: Name to store the processed text for later use
- **Variable Insert Button**: Easy insertion of workflow variables into all fields

### JSON Handler Node

The JSON Handler node manipulates and processes JSON data.

#### Features:
- JSON parsing and stringification
- Path-based value extraction
- JSON structure transformation
- Formatted output options
- **Variable name customization with insert button**
- **Path variable support**

#### Configuration:
- **Operation**: JSON operation to perform
- **Path**: JSON path for extraction (supports variables)
- **Format Output**: Whether to format JSON output
- **Default Value**: Default value if path is not found (supports variables)
- **Transform Keys**: Key mapping for transformations (supports variables)
- **Variable Name**: Name to store the JSON data for later use
- **Variable Insert Button**: Easy insertion of workflow variables into path expressions

### File Transformer Node

The File Transformer node converts file content between different formats.

#### Features:
- Text conversion with encoding options
- Base64 encoding/decoding
- JSON conversion for structured data
- Metadata extraction from files
- **Variable name customization with insert button**

#### Configuration:
- **Operation**: File operation to perform
- **Output Format**: Target format for conversion
- **Encoding**: Text encoding to use
- **Variable Name**: Name to store the transformed file for later use
- **Variable Insert Button**: Easy insertion of workflow variables

## Integration Nodes

### Gmail Trigger Node

The Gmail Trigger node triggers workflows based on Gmail events.

#### Features:
- New email detection
- Attachment detection
- Label-based filtering
- Query-based filtering
- **Variable name customization with insert button**
- **Filter criteria with variable support**

#### Configuration:
- **Trigger Type**: Type of Gmail event to trigger on
- **Labels**: Gmail labels to filter by
- **Filter**: Additional query criteria (supports variables)
- **Max Results**: Maximum number of emails to retrieve
- **Variable Name**: Name to store the email data for later use
- **Variable Insert Button**: Easy insertion of workflow variables into filters

### Outlook Trigger Node

The Outlook Trigger node triggers workflows based on Microsoft Outlook events.

#### Features:
- Email monitoring
- Calendar event tracking
- Folder-based organization
- Filter criteria support
- **Variable name customization with insert button**
- **Folder/filter with variable support**

#### Configuration:
- **Trigger Type**: Type of Outlook event to trigger on
- **Folder**: Outlook folder to monitor (supports variables)
- **Filter**: Filter criteria for items (supports variables)
- **Max Results**: Maximum number of items to retrieve
- **Include Attachments**: Whether to include attachments
- **Variable Name**: Name to store the Outlook data for later use
- **Variable Insert Button**: Easy insertion of workflow variables into folder/filter fields

### Notification Node

The Notification Node sends notifications through various channels.

#### Features:
- Multiple notification channels (email, Slack, webhook, SMS)
- Customizable message templates
- Priority settings
- Variable replacement in messages
- **Variable name customization with insert button**
- **Rich template support with variable insertion**

#### Configuration:
- **Notification Type**: Channel to send notifications through
- **Recipients**: List of recipients (supports variables)
- **Subject**: Notification subject line (supports variables)
- **Message**: Message template with variable support
- **Priority**: Notification priority
- **Variable Name**: Name to store the notification result for later use
- **Variable Insert Button**: Easy insertion of workflow variables into all message fields

### CRM Enricher Node

The CRM Enricher node enhances contact and company data with additional information.

#### Features:
- Contact data enrichment
- Company data enrichment
- Multiple data source support
- CRM-specific customization
- **Variable name customization with insert button**
- **Data source selection with variable support**

#### Configuration:
- **CRM Type**: Type of CRM system
- **Enrichment Type**: Type of data to enrich
- **Data Sources**: Sources to use for enrichment (supports variables)
- **Variable Name**: Name to store the enriched data for later use
- **Variable Insert Button**: Easy insertion of workflow variables into data source configurations

## Usage Guidelines

### Variable Naming and Insertion

All nodes now support:
1. **Custom variable naming** through the `variableName` parameter
2. **Variable Insert Buttons** for easy insertion of workflow variables into node configurations
3. **Variable reference syntax**: Use `{{variableName}}` to reference variables within fields

For example:
- Set a variable name like "sentiment_result" in the AI Task Executor node
- Reference it in a notification message using `{{sentiment_result.sentiment}}`
- Use the Variable Insert Button to easily add this reference without typing

### Input/Output Connections

Nodes can be connected by linking the output of one node to the input of another. The system automatically handles the data flow between nodes.

### Error Handling

All nodes include built-in error handling that:
1. Captures and logs errors
2. Provides meaningful error messages
3. Allows workflows to continue when possible
4. Stores error information for debugging

### State Persistence

The workflow system maintains state between node executions, allowing complex workflows with dependencies and data sharing between steps. 