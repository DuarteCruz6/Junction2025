@component
export class AsrExample extends BaseScriptComponent {
  @input('Component.ScriptComponent')
  apiClientScript: any;
  
  private asrModule = require('LensStudio:AsrModule');
  private isTranscribing = false;
  private apiClient: any = null;

  /**
   * Initialize the component and get API client reference
   */
  onAwake(): void {
    // Get API client from input script component
    // In Lens Studio, JavaScript scripts expose properties on the script object
    // We access it through the ScriptComponent input
    this.updateApiClientReference();
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
        
        // Try accessing apiClient directly (if exposed on script object)
        if (scriptObj.apiClient) {
          this.apiClient = scriptObj.apiClient;
          print('ASR: API client connected via input script (direct)');
          return;
        }
        
        // Try accessing through script context
        if (scriptObj.script && scriptObj.script.apiClient) {
          this.apiClient = scriptObj.script.apiClient;
          print('ASR: API client connected via script context');
          return;
        }
      }
      
      print('ASR: Warning - API client not found. Make sure to connect the apiClientScript input in Lens Studio.');
    } catch (error) {
      print(`ASR: Error accessing API client: ${error}`);
    }
  }

  /**
   * Start transcription session
   */
  startTranscribing(): void {
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
   */
  stopTranscribing(): void {
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

    // Send transcription to backend if API client is available
    if (this.apiClient && this.apiClient.currentMeetingId) {
      try {
        await this.apiClient.sendTranscription(text, isFinal, "Unknown");
        if (isFinal) {
          print(`ASR: Final transcription sent to backend: "${text}"`);
        }
      } catch (error) {
        print(`ASR: Error sending transcription to backend: ${error}`);
      }
    } else {
      // If no API client or no active meeting, just log (only for final transcriptions to reduce spam)
      if (isFinal) {
        if (!this.apiClient) {
          print('ASR: API client not available, transcription not sent');
        } else if (!this.apiClient.currentMeetingId) {
          print('ASR: No active meeting, transcription not sent');
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