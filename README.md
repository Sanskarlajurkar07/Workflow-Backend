<<<<<<< HEAD
# Workflow Automation Backend

This is the backend server for the Workflow Automation platform.

## Enhanced Workflow Nodes

The system includes several specialized workflow nodes for complex automation:

### Condition Node
- Supports complex decision logic with multiple paths
- Now includes regex pattern matching and date comparisons
- Handles nested object fields using dot notation

### Merge Node
- Combines data from multiple workflow paths
- Supports strategies like "Pick First", "Join All", "Concatenate Arrays", and "Merge Objects"
- Custom delimiters for text joins

### Time Node
- Provides timezone-aware time operations
- Supports time arithmetic (add/subtract time units)
- Custom format strings for date/time display
- Extended time information (DST status, UTC offset, etc.)

### Text to SQL Node
- Converts natural language to SQL queries
- Parameter support for query customization
- SQL validation to catch errors
- Optional SQL execution capabilities

See the [documentation](docs/workflow_nodes.md) for detailed information.

## Node System Upgrade

The workflow automation system has been enhanced with a new node system that includes:

- **AI Tools & SparkLayer**: Advanced AI capabilities using various providers
- **Chat Memory**: Persistent chat history for contextual conversations
- **Data Collection & Processing**: Text, JSON, and file handling nodes
- **Email Integration**: Gmail and Outlook triggers
- **Notification Services**: Multi-channel notification support
- **CRM Enrichment**: Contact and company data enrichment

The node system has been completely redesigned with a user-centric approach:

- **Consistent variable naming**: Every node has customizable variable names
- **Variable Insert Buttons**: One-click insertion of variables into any field
- **Variable Reference System**: Easy `{{variable}}` syntax for rich templating
- **Improved error handling**: Detailed error messages and recovery options
- **Enhanced documentation**: Complete usage guides for each node
- **Visual cues**: Better UI indicators for variable usage

For detailed information about all available nodes, see the [Updated Nodes Documentation](./UPDATED_NODES.md).

### Implementation Details

The node system is implemented with a modular architecture:

- `node_handlers.py`: Core node execution and registration
- `ai_node_handlers.py`: AI-related nodes
- `integration_node_handlers.py`: Integration with external services
- `data_node_handlers.py`: Data processing nodes
- `chat_memory_node.py`, `data_collector_node.py`: Specialized node implementations

Each node follows a standard pattern that includes:
1. Parameter extraction from node configuration
2. Variable name processing and storage
3. Input processing with variable substitution
4. Operation execution
5. Result formatting
6. Variable registration for downstream use

## Setup for Public Deployment

For public deployment, follow these steps to ensure users don't need to enter their own API keys:

1. **Environment Setup**
   - Copy `env.example` to `.env` 
   - Configure your MongoDB and other database settings
   - **IMPORTANT**: Set at least one AI service API key (OPENAI_API_KEY recommended)

2. **API Key Management**
   - For public deployment, you should provide a system-wide API key
   - Set `OPENAI_API_KEY` in the `.env` file with your valid OpenAI API key
   - Users can leave the API Key field blank in the OpenAI node to use your system API key

3. **Starting the Server**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Start the server
   python main.py
   ```

4. **Customizing Rate Limits**
   If you want to add rate limits for public use, you can modify the code to add:
   - Daily token limits per user
   - Request rate limiting
   - Model access restrictions

## Security Considerations

For public deployments:
1. Never expose your `.env` file
2. Set a strong JWT_SECRET_KEY
3. Enable authentication for all routes
4. Consider adding user quotas to prevent excessive API usage
5. Monitor usage to prevent abuse

## Troubleshooting

If users report no outputs from AI nodes:
1. Check that OPENAI_API_KEY is set in the `.env` file
2. Verify the API key is valid and has sufficient credits
3. Check the logs for any API errors
4. Ensure the networking allows outbound connections to OpenAI servers 

## Examples and Testing

To try out the enhanced workflow nodes:

1. Run the demo script:
   ```bash
   python examples/workflow_nodes_demo.py
   ```

2. Run the test suite:
   ```bash
   pytest tests/test_workflow_nodes.py
   ``` 
=======
# Workflow-Backend
>>>>>>> c31bc636ad0da83280dbff20ae352441e97f984e
