document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('import-container')) {
        setupImportEventListeners();
    }
});

function setupImportEventListeners() {
    // Import form submission
    document.getElementById('import-form').addEventListener('submit', function(e) {
        e.preventDefault();
        importMusic();
    });
    
    // Clear output button
    document.getElementById('clear-output').addEventListener('click', function() {
        document.getElementById('import-output').value = '';
    });
}

function importMusic() {
    const pathInput = document.getElementById('path-input');
    const importOutput = document.getElementById('import-output');
    const importButton = document.getElementById('import-button');
    
    const path = pathInput.value.trim();
    if (!path) {
        showError('Please enter a path to import');
        return;
    }
    
    // Set button to loading state
    setButtonLoading(importButton, true);
    
    // Append command to output
    importOutput.value += `\n> Importing music from: ${path}\n`;
    
    // Make API request to import music
    fetch('/api/import', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ path: path })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to import music');
        }
        return response.json();
    })
    .then(data => {
        // Set button back to normal state
        setButtonLoading(importButton, false);
        
        // Append import output
        if (data.result.stdout) {
            importOutput.value += data.result.stdout;
        }
        
        if (data.result.stderr) {
            importOutput.value += `Error: ${data.result.stderr}\n`;
        }
        
        // Scroll to bottom of output
        importOutput.scrollTop = importOutput.scrollHeight;
        
        // Show success message if import was successful
        if (data.result.success) {
            showSuccess('Music imported successfully');
        } else {
            showError('Music import failed');
        }
    })
    .catch(error => {
        console.error('Error importing music:', error);
        showError('Failed to import music: ' + error.message);
        
        // Set button back to normal state
        setButtonLoading(importButton, false);
        
        // Append error to output
        importOutput.value += `Error: ${error.message}\n`;
        importOutput.scrollTop = importOutput.scrollHeight;
    });
}
