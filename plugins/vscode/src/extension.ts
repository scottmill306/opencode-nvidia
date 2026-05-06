import * as vscode from 'vscode';
import axios from 'axios';
let apiEndpoint: string = 'http://localhost:8080';

// Shared state for inline completions — updated by completeCode()
let pendingCompletion: vscode.InlineCompletionItem[] = [];

// Shared diagnostic collection — created once in activate()
let securityDiagnostics: vscode.DiagnosticCollection;

export function activate(context: vscode.ExtensionContext) {
    console.log('OpenCode NVIDIA extension is now active!');

    // Get API endpoint from configuration
    const config = vscode.workspace.getConfiguration('opencode');
    apiEndpoint = config.get('apiEndpoint', 'http://localhost:8080');

    // Register the inline completions provider once and add it to subscriptions
    context.subscriptions.push(
        vscode.languages.registerInlineCompletionsProvider(
            { pattern: '**' },
            {
                provideInlineCompletions: () => ({
                    items: pendingCompletion,
                    dispose: () => {}
                })
            }
        )
    );

    // Register the diagnostic collection once and add it to subscriptions
    securityDiagnostics = vscode.languages.createDiagnosticCollection('opencode-security');
    context.subscriptions.push(securityDiagnostics);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('opencode.generate', generateCode)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('opencode.complete', completeCode)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('opencode.securityScan', securityScan)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('opencode.refactor', refactorCode)
    );

    // Auto security scan on save
    if (config.get('autoSecurityScan', true)) {
        context.subscriptions.push(
            vscode.workspace.onDidSaveTextDocument(async (document) => {
                await performSecurityScan(document);
            })
        );
    }
}

async function generateCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    const selectedText = editor.document.getText(selection);
    
    if (!selectedText) {
        vscode.window.showInformationMessage('Please select code to generate from');
        return;
    }

    const prompt = await vscode.window.showInputBox({
        prompt: 'What would you like to generate?',
        placeHolder: 'e.g., Add error handling, Create a REST endpoint...'
    });

    if (!prompt) {
        return;
    }

    try {
        const response = await axios.post(`${apiEndpoint}/generate`, {
            prompt: `${selectedText}\n\n# ${prompt}`,
            max_tokens: vscode.workspace.getConfiguration('opencode').get('maxTokens', 256),
            stream: vscode.workspace.getConfiguration('opencode').get('enableStreaming', true)
        });

        const generatedCode = response.data.generated_code;
        
        // Insert generated code after selection
        const position = new vscode.Position(selection.end.line, selection.end.character);
        editor.edit(editBuilder => {
            editBuilder.insert(position, `\n\n${generatedCode}`);
        });

        vscode.window.showInformationMessage(`✅ Code generated in ${response.data.latency_ms}ms`);
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to generate code: ${error.message}`);
    }
}

async function completeCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return;
    }

    const position = editor.selection.active;
    const linePrefix = editor.document.lineAt(position).text.slice(0, position.character);

    try {
        const response = await axios.post(`${apiEndpoint}/complete`, {
            prompt: linePrefix,
            max_tokens: 50,
            temperature: 0.3
        });

        const completion = response.data.generated_code;

        // Update shared state; the provider registered once in activate() will serve this
        pendingCompletion = [new vscode.InlineCompletionItem(completion)];
        await vscode.commands.executeCommand('editor.action.inlineSuggest.trigger');
    } catch (error: any) {
        console.error('Completion error:', error);
    }
}

async function securityScan() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return;
    }

    await performSecurityScan(editor.document);
}

async function performSecurityScan(document: vscode.TextDocument) {
    const code = document.getText();
    const language = document.languageId;

    try {
        const response = await axios.post(`${apiEndpoint}/security/scan`, {
            code: code,
            language: language
        });

        const result = response.data;
        
        if (result.vulnerabilities.length === 0) {
            vscode.window.showInformationMessage('✅ No security vulnerabilities detected');
            return;
        }

        // Show vulnerabilities in diagnostics panel
        const diagCollection = securityDiagnostics;
        const diagnostics: vscode.Diagnostic[] = [];

        result.vulnerabilities.forEach((vuln: any) => {
            const line = vuln.line >= 0 ? vuln.line : 0;
            const range = new vscode.Range(line, 0, line, 100);
            const diagnostic = new vscode.Diagnostic(
                range,
                `[${vuln.severity.toUpperCase()}] ${vuln.description}`,
                vuln.severity === 'critical' ? vscode.DiagnosticSeverity.Error :
                vuln.severity === 'high' ? vscode.DiagnosticSeverity.Warning :
                vscode.DiagnosticSeverity.Information
            );
            diagnostics.push(diagnostic);
        });

        diagCollection.set(document.uri, diagnostics);

        // Show summary message
        vscode.window.showWarningMessage(
            `⚠️ Found ${result.vulnerabilities.length} security issue(s). Risk level: ${result.risk_level.toUpperCase()}`
        );

        // Show suggestions
        if (result.suggestions.length > 0) {
            const suggestion = await vscode.window.showInformationMessage(
                'Security suggestions available',
                'View Suggestions'
            );
            
            if (suggestion === 'View Suggestions') {
                const panel = vscode.window.createWebviewPanel(
                    'securitySuggestions',
                    'Security Suggestions',
                    vscode.ViewColumn.One,
                    {}
                );
                panel.webview.html = `
                    <html>
                        <body>
                            <h2>Security Suggestions</h2>
                            <ul>
                                ${result.suggestions.map((s: string) => `<li>${s}</li>`).join('')}
                            </ul>
                        </body>
                    </html>
                `;
            }
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Security scan failed: ${error.message}`);
    }
}

async function refactorCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return;
    }

    const selection = editor.selection;
    const selectedText = editor.document.getText(selection);

    if (!selectedText) {
        vscode.window.showInformationMessage('Please select code to refactor');
        return;
    }

    try {
        const response = await axios.post(`${apiEndpoint}/refactor`, {
            prompt: selectedText
        });

        const result = response.data;
        
        // Show refactoring results
        const panel = vscode.window.createWebviewPanel(
            'refactorResults',
            'GPU Refactoring Results',
            vscode.ViewColumn.Beside,
            {}
        );

        panel.webview.html = `
            <html>
                <head>
                    <style>
                        body { font-family: var(--vscode-font-family); padding: 20px; }
                        .improvement { background: var(--vscode-editor-background); padding: 10px; margin: 10px 0; border-radius: 5px; }
                        .performance { color: var(--vscode-terminal-ansiGreen); font-weight: bold; }
                        pre { background: var(--vscode-textCodeBlock-background); padding: 10px; border-radius: 5px; overflow-x: auto; }
                    </style>
                </head>
                <body>
                    <h2>🚀 GPU Optimization Results</h2>
                    <p class="performance">Performance Gain: ${result.performance_gain}</p>
                    
                    <h3>Improvements:</h3>
                    ${result.improvements.map((imp: string) => `<div class="improvement">✓ ${imp}</div>`).join('')}
                    
                    <h3>Refactored Code:</h3>
                    <pre><code>${result.refactored_code}</code></pre>
                </body>
            </html>
        `;

        vscode.window.showInformationMessage('✅ Refactoring complete! View results in the side panel.');
    } catch (error: any) {
        vscode.window.showErrorMessage(`Refactoring failed: ${error.message}`);
    }
}

export function deactivate() {
    console.log('OpenCode NVIDIA extension deactivated');
}
