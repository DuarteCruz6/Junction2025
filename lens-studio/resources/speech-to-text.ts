@component
export class AsrExample extends BaseScriptComponent {
  @input('Component.ScriptComponent')
  apiClientScript: any;
  
  private asrModule = require('LensStudio:AsrModule');
  private isTranscribing = false;
  private apiClient: any = null;
  
  // Public methods - accessible directly from JavaScript
  // These can be called via script.asrScript.startTranscribing() etc.

  /**
   * Initialize the component and get API client reference
   */
  onAwake(): void {
    // Force print to verify component is loading
    print('=== ASR Component: onAwake() called ===');
    
    // Get API client from input script component
    // In Lens Studio, JavaScript scripts expose properties on the script object
    // We access it through the ScriptComponent input
    this.updateApiClientReference();
    
    print('=== ASR Component: Initialization complete ===');
  }

  /**
   * Update API client reference (can be called multiple times)
   */
  private updateApiClientReference(): void {
    try {
      // Access through the input script component
      // The JavaScript script sets script.apiClient, which should be accessible
      if (this.apiClientScript) {
        const scriptObj = (this.apiClientScript as any);
        
        // Method 1: Try accessing through script.apiClient (JavaScript exposes it this way)
        // In Lens Studio, JavaScript scripts expose properties via the script object
        // We need to get the script context from the ScriptComponent
        try {
          // Access the script object from the ScriptComponent
          // The ScriptComponent has a reference to the script context
          if (scriptObj.script && scriptObj.script.apiClient) {
            this.apiClient = scriptObj.script.apiClient;
            print('ASR: API client connected via script.apiClient');
            return;
          }
        } catch (e) {
          // Continue to next method
        }
        
        // Method 2: Try accessing apiClient directly on the component
        if (scriptObj.apiClient) {
          this.apiClient = scriptObj.apiClient;
          print('ASR: API client connected via direct property');
          return;
        }
        
        // Method 3: Try getting the script via getScript() if available
        if (typeof scriptObj.getScript === 'function') {
          try {
            const script = scriptObj.getScript();
            if (script && script.apiClient) {
              this.apiClient = script.apiClient;
              print('ASR: API client connected via getScript()');
              return;
            }
          } catch (e) {
            // Continue
          }
        }
      }
      
      print('ASR: Warning - API client not found. Make sure to connect the apiClientScript input in Lens Studio.');
    } catch (error) {
      print(`ASR: Error accessing API client: ${error}`);
    }
  }

  /**
   * Start transcription session
   * Public method accessible from JavaScript
   */
  public startTranscribing(): void {
    if (this.isTranscribing) {
      print('ASR: Already transcribing');
      return;
    }

    try {
      const options = AsrModule.AsrTranscriptionOptions.create();
      options.silenceUntilTerminationMs = 1000;
      options.mode = AsrModule.AsrMode.HighAccuracy;
      options.onTranscriptionUpdateEvent.add((eventArgs) =>
        this.onTranscriptionUpdate(eventArgs)
      );
      options.onTranscriptionErrorEvent.add((eventArgs) =>
        this.onTranscriptionError(eventArgs)
      );

      this.asrModule.startTranscribing(options);
      this.isTranscribing = true;
      print('ASR: Transcription started');
    } catch (error) {
      print(`ASR: Error starting transcription: ${error}`);
      this.isTranscribing = false;
    }
  }

  /**
   * Stop transcription session
   * Public method accessible from JavaScript
   */
  public stopTranscribing(): void {
    if (!this.isTranscribing) {
      return;
    }

    try {
      this.asrModule.stopTranscribing();
      this.isTranscribing = false;
      print('ASR: Transcription stopped');
    } catch (error) {
      print(`ASR: Error stopping transcription: ${error}`);
    }
  }

  /**
   * Handle transcription updates from Lens Studio ASR
   */
  private async onTranscriptionUpdate(eventArgs: AsrModule.TranscriptionUpdateEvent) {
    const text = eventArgs.text;
    const isFinal = eventArgs.isFinal;

    print(`ASR: Transcription update - text="${text}", isFinal=${isFinal}`);

    // Try to get API client if not already set (retry on each update)
    if (!this.apiClient) {
      this.updateApiClientReference();
    }

    // Debug: Log current state
    if (isFinal) {
      print(`ASR: Debug - apiClient exists: ${!!this.apiClient}, meetingId: ${this.apiClient ? this.apiClient.currentMeetingId : 'N/A'}`);
    }

    // Send transcription to backend if API client is available
    if (this.apiClient && this.apiClient.currentMeetingId) {
      try {
        print(`ASR: Sending transcription to backend - meetingId: ${this.apiClient.currentMeetingId}, text: "${text}"`);
        const result = await this.apiClient.sendTranscription(text, isFinal, "Unknown");
        if (isFinal) {
          print(`ASR: Final transcription sent to backend: "${text}", result: ${JSON.stringify(result)}`);
        }
      } catch (error) {
        print(`ASR: Error sending transcription to backend: ${error}`);
        // Also log the full error details
        if (error && error.message) {
          print(`ASR: Error details: ${error.message}`);
        }
      }
    } else {
      // If no API client or no active meeting, log the issue
      if (isFinal) {
        if (!this.apiClient) {
          print('ASR: ERROR - API client not available, transcription not sent');
        } else if (!this.apiClient.currentMeetingId) {
          print(`ASR: ERROR - No active meeting (currentMeetingId is ${this.apiClient.currentMeetingId}), transcription not sent`);
          print('ASR: Make sure to start a meeting before speaking');
        }
      }
    }
  }

  /**
   * Handle transcription errors
   */
  private onTranscriptionError(eventArgs: AsrModule.AsrStatusCode) {
    print(`ASR: Transcription error - code: ${eventArgs}`);
    this.isTranscribing = false;

    switch (eventArgs) {
      case AsrModule.AsrStatusCode.InternalError:
        print('ASR: Internal Error - stopping transcription');
        break;
      case AsrModule.AsrStatusCode.Unauthenticated:
        print('ASR: Unauthenticated - check API credentials');
        break;
      case AsrModule.AsrStatusCode.NoInternet:
        print('ASR: No Internet connection');
        break;
      default:
        print(`ASR: Unknown error code: ${eventArgs}`);
    }
  }

  /**
   * Public API for external control
   */
  public getIsTranscribing(): boolean {
    return this.isTranscribing;
  }
}