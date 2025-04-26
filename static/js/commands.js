document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('command-container')) {
        setupCommandEventListeners();
        populateCommonCommands();
    }
});

function setupCommandEventListeners() {
    // Command execution form
    document.getElementById('command-form').addEventListener('submit', function(e) {
        e.preventDefault();
        executeCommand();
    });
    
    // Common command selection
    document.getElementById('common-commands').addEventListener('change', function() {
        const selectedCommand = this.value;
        if (selectedCommand) {
            document.getElementById('command-input').value = selectedCommand;
        }
    });
    
    // Clear output button
    document.getElementById('clear-output').addEventListener('click', function() {
        document.getElementById('command-output').value = '';
    });
}

function populateCommonCommands() {
    const commonCommands = [
        { value: 'list', label: 'List all tracks' },
        { value: 'list -a', label: 'List all albums' },
        { value: 'stats', label: 'Show library statistics' },
        { value: 'info', label: 'Show file metadata' },
        { value: 'modify', label: 'Modify metadata' },
        { value: 'update', label: 'Update library' },
        { value: 'move', label: 'Move items in library' },
        { value: 'write', label: 'Write metadata to files' },
        { value: 'duplicates', label: 'List duplicate tracks' },
        { value: 'config', label: 'Show configuration' }
    ];
    
    const selectElement = document.getElementById('common-commands');
    
    // Add default empty option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select a common command...';
    selectElement.appendChild(defaultOption);
    
    // Add common commands
    commonCommands.forEach(cmd => {
        const option = document.createElement('option');
        option.value = cmd.value;
        option.textContent = cmd.label;
        selectElement.appendChild(option);
    });
}

function executeCommand() {
    const commandInput = document.getElementById('command-input');
    const commandOutput = document.getElementById('command-output');
    const executeButton = document.getElementById('execute-button');
    
    const command = commandInput.value.trim();
    if (!command) {
        showError('Please enter a command to execute');
        return;
    }
    
    // Set button to loading state
    setButtonLoading(executeButton, true);
    
    // Append command to output
    commandOutput.value += `\n> beet ${command}\n`;
    
    // Make API request to execute the command
    fetch('/api/command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command: command })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to execute command');
        }
        return response.json();
    })
    .then(data => {
        // Set button back to normal state
        setButtonLoading(executeButton, false);
        
        // Append command output
        if (data.result.stdout) {
            commandOutput.value += data.result.stdout;
        }
        
        if (data.result.stderr) {
            commandOutput.value += `Error: ${data.result.stderr}\n`;
        }
        
        // Scroll to bottom of output
        commandOutput.scrollTop = commandOutput.scrollHeight;
        
        // Show success message if command executed successfully
        if (data.result.success) {
            showSuccess('Command executed successfully');
        } else {
            showError('Command execution failed');
        }
    })
    .catch(error => {
        console.error('Error executing command:', error);
        showError('Failed to execute command: ' + error.message);
        
        // Set button back to normal state
        setButtonLoading(executeButton, false);
        
        // Append error to output
        commandOutput.value += `Error: ${error.message}\n`;
        commandOutput.scrollTop = commandOutput.scrollHeight;
    });
}
