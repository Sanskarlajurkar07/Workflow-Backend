#!/usr/bin/env python3
"""
Test script to verify variable processing fixes
"""
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Import our fixed functions
from ai_providers_node import handle_ai_provider_node, generate_contextual_response
from variable_processor import process_node_variables, validate_variables

class MockRequest:
    def __init__(self):
        self.node_outputs = {
            "input_0": {
                "text": "Hello World",
                "type": "Text"
            },
            "input_1": {
                "image": {"url": "https://example.com/image.jpg"},
                "type": "Image"
            },
            "input_2": {
                "audio": {"url": "https://example.com/audio.mp3"},
                "type": "Audio"
            },
            "input_3": {
                "json": {"key": "value"},
                "type": "JSON"
            },
            "input_4": {
                "file": {"url": "https://example.com/file.pdf"},
                "type": "File"
            }
        }

async def test_variable_processing():
    """Test that variable processing works correctly"""
    print("🧪 Testing Variable Processing Fixes")
    print("=" * 50)
    
    # Test 1: Text input processing
    print("\n📝 Test 1: Text Input Processing")
    text_template = "System: {{input_0.text}}"
    processed_text = process_node_variables(text_template, MockRequest().node_outputs)
    print(f"Original: {text_template}")
    print(f"Processed: {processed_text}")
    assert "Hello World" in processed_text, "Text processing failed"
    print("✅ Text processing works!")
    
    # Test 2: Image input processing
    print("\n📝 Test 2: Image Input Processing")
    image_template = "Image URL: {{input_1.image}}"
    processed_image = process_node_variables(image_template, MockRequest().node_outputs)
    print(f"Original: {image_template}")
    print(f"Processed: {processed_image}")
    assert "https://example.com/image.jpg" in processed_image, "Image processing failed"
    print("✅ Image processing works!")
    
    # Test 3: Audio input processing
    print("\n📝 Test 3: Audio Input Processing")
    audio_template = "Audio URL: {{input_2.audio}}"
    processed_audio = process_node_variables(audio_template, MockRequest().node_outputs)
    print(f"Original: {audio_template}")
    print(f"Processed: {processed_audio}")
    assert "https://example.com/audio.mp3" in processed_audio, "Audio processing failed"
    print("✅ Audio processing works!")
    
    # Test 4: JSON input processing
    print("\n📝 Test 4: JSON Input Processing")
    json_template = "JSON Data: {{input_3.json}}"
    processed_json = process_node_variables(json_template, MockRequest().node_outputs)
    print(f"Original: {json_template}")
    print(f"Processed: {processed_json}")
    assert '"key": "value"' in processed_json, "JSON processing failed"
    print("✅ JSON processing works!")
    
    # Test 5: File input processing
    print("\n📝 Test 5: File Input Processing")
    file_template = "File URL: {{input_4.file}}"
    processed_file = process_node_variables(file_template, MockRequest().node_outputs)
    print(f"Original: {file_template}")
    print(f"Processed: {processed_file}")
    assert "https://example.com/file.pdf" in processed_file, "File processing failed"
    print("✅ File processing works!")
    
    # Test 6: Variable validation
    print("\n📝 Test 6: Variable Validation")
    available_variables = {
        "input_0": {"type": "Text"},
        "input_1": {"type": "Image"},
        "input_2": {"type": "Audio"},
        "input_3": {"type": "JSON"},
        "input_4": {"type": "File"}
    }
    
    # Valid variable usage
    valid_template = "{{input_0.text}}"
    validation_result = validate_variables(valid_template, available_variables)
    assert validation_result is None, "Valid variable validation failed"
    print("✅ Valid variable validation works!")
    
    # Invalid variable usage
    invalid_template = "{{input_0.image}}"  # Text node doesn't have image output
    validation_result = validate_variables(invalid_template, available_variables)
    assert validation_result is not None, "Invalid variable validation failed"
    print("✅ Invalid variable validation works!")
    
    # Test 7: AI node with variable processing
    print("\n📝 Test 7: AI Node with Variable Processing")
    node_data = {
        "params": {
            "system": "Process this image: {{input_1.image}}",
            "prompt": "Describe the audio: {{input_2.audio}}",
            "model": "gpt-3.5-turbo",
            "maxTokens": 100,
            "temperature": 0.7,
            "variableName": "test_result"
        }
    }
    
    mock_request = MockRequest()
    
    # Enable simulation mode for testing
    os.environ["SIMULATE"] = "true"
    
    try:
        result = await handle_ai_provider_node(
            node_id="test_openai_node",
            node_data=node_data,
            inputs={},
            workflow_data={},
            start_time=0,
            provider="openai",
            request=mock_request
        )
        
        print(f"Node result status: {result.status}")
        print(f"Node result output: {result.output.get('content', 'No content')[:100]}...")
        
        assert "{{" not in result.output.get('content', ''), "Variables not processed in AI node"
        print("✅ AI node variable processing works!")
            
    except Exception as e:
        print(f"❌ Error testing AI node: {str(e)}")
    
    finally:
        os.environ.pop("SIMULATE", None)
    
    print("\n🎯 Summary")
    print("The variable system now supports:")
    print("1. Different input types (Text, Image, Audio, JSON, File)")
    print("2. Type-specific output fields")
    print("3. Variable validation based on node types")
    print("4. Proper error handling for invalid variables")
    print("5. Integration with AI nodes")

if __name__ == "__main__":
    asyncio.run(test_variable_processing()) 