# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DG-LAB-VRCOSC is a Python desktop application that controls DG-LAB 3.0 devices through VRChat OSC integration and Terrors of Nowhere game events. The application uses a PySide6 GUI with asyncio for handling both WebSocket and Bluetooth connections to DG-LAB hardware and external game integrations.

### Connection Methods
- **WebSocket**: Primary connection method via DG-LAB app's socket control
- **Bluetooth (In Development)**: Direct Bluetooth Low Energy (BLE) connection to DG-LAB 3.0 devices

### Development Branches
- **master**: Stable release branch with WebSocket functionality
- **dev-bluetooth**: Active development branch with Bluetooth LE implementation

## Development Commands

### Installation and Setup
```bash
# Clone and setup environment
git clone https://github.com/MofuNadenade/DG-LAB-VRCOSC.git
cd DG-LAB-VRCOSC
python -m venv .venv
.venv\Scripts\activate.bat  # Windows Command Prompt
pip install -r requirements.txt
```

### Running the Application
```bash
# Development mode
python src/app.py

# Development mode with file watching and auto-rebuild
python scripts/dev_build.py --watch

# Run with debug logging
python src/app.py --debug
```

### Build System
The project uses an automated build system with scripts for different scenarios:

**Quick Development Build:**
```bash
python scripts/dev_build.py
```

**Full Production Build:**
```bash
python scripts/build.py
```

**Clean Build (removes previous build artifacts):**
```bash
python scripts/build.py --clean
```

**Version Generation Only:**
```bash
python scripts/generate_version.py
```

### Testing and Development Utilities
```bash
# Test Bluetooth client (development/debugging)
python src/test_bluetooth_client.py

# Internationalization management
python scripts/i18n_manager.py analyze      # Analyze localization key usage
python scripts/i18n_manager.py check        # Check language file consistency
python scripts/i18n_manager.py find-unused  # Find unused translation keys

# Internationalization validation
python scripts/i18n_checker.py              # Basic consistency check
python scripts/i18n_checker.py --details    # Detailed key comparison
```

### Code Quality and Type Checking
**Critical**: All builds include automatic type checking that must pass:

```bash
# Run type checking on all typed modules (required before builds)
python -m pyright src/

# Check version information
python scripts/generate_version.py --check
```

### VSCode Integration
The project includes comprehensive VSCode configuration:

**Available Tasks (Ctrl+Shift+P → "Tasks: Run Task"):**
- Generate Version
- Type Check
- Build Application  
- Development Build
- Clean Build

**Debug Configurations:**
- DG-LAB-VRCOSC (main application with pre-launch version generation)
- Generate Version Only
- Build Application

## Architecture Overview

### Core Components

1. **Entry Point** (`src/app.py`): Sets up the Qt application with asyncio event loop integration using qasync
2. **Main UI** (`src/gui/main_window.py`): PySide6-based main window with tabbed interface using service controller pattern
3. **Service Controller** (`src/core/service_controller.py`): Central orchestration of all services with ordered startup/shutdown
4. **Services Architecture** (`src/services/`): Modular service-based architecture with separated concerns
5. **OSC System** (`src/core/`): Registry-based OSC parameter and action binding system with three-layer architecture
6. **Configuration** (`src/config.py`): YAML-based settings management with network interface detection

### Layered Architecture: Protocol Layer vs Service Layer

The application uses a clear separation between protocol layer and service layer:

#### Protocol Layer (`src/core/`)
Low-level device communication and protocol implementation:

- **WebSocket Protocol** (`src/core/websocket/`):
  - `WebSocketController`: WebSocket connection management and frame transmission
  - `WebSocketChannelStateHandler`: Frame buffering and playback control with loop support
  - `WebSocketModels`: Data models including `PlaybackMode` enum for frame playback modes
  - Frame-level operations using 100ms time slices

- **Bluetooth Protocol** (`src/core/bluetooth/`):
  - `BluetoothController`: Direct BLE communication with DG-LAB 3.0 devices
  - `BluetoothChannelStateHandler`: Frame buffering and playback control with loop support  
  - `BluetoothModels`: Strong-typed data models including `PlaybackMode` enum
  - V3 protocol implementation with B0/BF command processing

#### Service Layer (`src/services/`)
High-level business logic and application services:

- **DGLabWebSocketService**: WebSocket-based DG-LAB hardware control (strength, channels, pulses, fire mode)
- **DGLabBluetoothService**: Direct Bluetooth LE communication with DG-LAB devices via `bleak` library
- **OSCService**: OSC message processing and VRChat communication
- **ChatboxService**: VRChat ChatBox status display and periodic updates
- **OSCActionService**: Business logic for all OSC actions, independent of device connection type

**Key Distinction**: Protocol layer handles frame-by-frame device communication with playback modes (ONCE/LOOP), while service layer provides high-level abstractions for application features.

### Key Architectural Patterns

- **Service-Oriented Architecture**: All business logic separated into specialized services (`src/services/`)
- **Registry Pattern**: OSC parameters and actions use centralized registries for mapping
- **Abstract Base Classes**: All interfaces use ABC with `@abstractmethod` decorators (not Protocol)
- **Async/Await**: Heavy use of asyncio for WebSocket and network operations
- **Event-Driven**: OSC parameter changes trigger bound actions through the registry system

### Services Architecture

The application uses a service-based architecture where the controller is a pure data container:

#### ServiceController (`src/core/service_controller.py`)
- **Service Orchestration**: Manages the lifecycle of all services in the correct order
- **Service References**: `dglab_device_service`, `osc_service`, `osc_action_service`, `chatbox_service`
- **Unified Management**: Single point for starting/stopping all services
- **Error Handling**: If any service fails to start, all previously started services are stopped in reverse order

#### Core Services (`src/services/`)
- **DGLabWebSocketService**: WebSocket-based DG-LAB hardware control (strength, channels, pulses, fire mode)
- **DGLabBluetoothService**: Direct Bluetooth LE communication with DG-LAB devices via `bleak` library
- **OSCService**: OSC message processing and VRChat communication
- **ChatboxService**: VRChat ChatBox status display and periodic updates
- **OSCActionService**: Business logic for all OSC actions, independent of device connection type

**CRITICAL**: All services inherit from abstract base classes (ABC), not Protocol:

```python
# Correct usage
class MyService(IService):  # Inherits from ABC
    @abstractmethod
    async def start_service(self) -> bool:
        ...  # Use ellipsis, not pass
```

#### Service Startup Order
Services are started in a specific order managed by ServiceController:
1. DG-Lab Device Service (WebSocket or Bluetooth)
2. OSC Service 
3. OSC Action Service
4. ChatBox Service

If any service fails, all previously started services are stopped in reverse order.

### Interface Architecture

All interfaces use Abstract Base Classes (ABC) with `@abstractmethod` decorators:

- **IService**: Base service interface for lifecycle management
- **IDGLabDeviceService**: Hardware abstraction for different connection types (WebSocket, Bluetooth)
- **CoreInterface**: Core functionality interface for logging, state management
- **UIInterface**: UI operations interface extending CoreInterface

### Frame Playback System

Both protocol layers implement a unified frame playback system:

#### Playback Modes
- **PlaybackMode.ONCE**: Play frame sequence once then stop
- **PlaybackMode.LOOP**: Continuously loop frame sequence

#### Frame Management
- **Frame Buffering**: 100ms time slices with synchronized A/B channel data
- **Logical Frame Position**: Tracks playback progress for UI updates  
- **Buffer Frame Position**: Handles actual data transmission timing
- **Automatic Completion Detection**: Stops playback when frame sequence ends (ONCE mode)
- **Loop Support**: Seamlessly restarts from beginning (LOOP mode)

#### Key Methods
- `advance_buffer_for_send()`: Advances buffer and returns frame data for transmission
- `advance_logical_frame()`: Updates logical playback position for progress tracking
- `is_frame_sequence_finished()`: Checks if playback completed (respects loop mode)
- `set_playback_mode()`: Configures ONCE/LOOP playback behavior

### OSC Parameter System

The application uses a three-layer OSC binding system (`src/core/registries.py`):
- **OSCAddressRegistry**: Maps parameter names to OSC codes
- **OSCActionRegistry**: Maps action names to callback functions  
- **OSCBindingRegistry**: Binds parameters to actions for event handling

**Template System** (`src/core/osc_template.py`): Provides pre-configured OSC templates for:
- VRChat contact/physbone interactions
- SoundPad button controls  
- PCS (Penetration Contact System) compatibility
- Custom user-defined bindings

### Configuration System

Settings are stored in `settings.yml` with defaults defined in `config.py`. The system includes:
- Network interface detection and validation
- OSC parameter binding configuration
- Custom pulse pattern definitions
- Automatic settings file generation

### Internationalization System

The application has full i18n support implemented in `src/i18n.py`:
- **Language Support**: Chinese (default), English, Japanese
- **Translation Files**: Located in `src/locales/` as YAML files (`zh.yml`, `en.yml`, `ja.yml`)
- **Translation Function**: Use `_("translation.key")` to access translations with dot-notation for nested keys
- **Language Switching**: Runtime language changes with UI updates via signal system
- **Resource Path**: Uses `resource_path()` function to handle both development and packaged environments

### External Integrations

- **VRChat OSC**: Receives parameters via UDP for avatar interactions
- **DG-LAB WebSocket**: Controls hardware via pydglab-ws library
- **DG-LAB Bluetooth**: Direct BLE communication using bleak library
- **Terrors of Nowhere**: Integrates with ToNSaveManager WebSocket API for game events (`src/ton_websocket_handler.py`)

### GUI Architecture

The main window (`src/gui/main_window.py`) implements a tabbed interface:
- **ConnectionTab**: Device connection management (WebSocket and Bluetooth)
- **PulseTab**: Pulse pattern creation and editing with visual waveform editor
- **OSCTab**: OSC address and binding management
- **SettingsTab**: Application settings and device control configuration
- **TonTab**: Terrors of Nowhere game integration
- **AboutTab**: Application information, version details, and feedback links
- **DebugTab**: Application logging and debugging

Each tab is a separate component that communicates with services through the controller.

### Build System Architecture

The project uses a comprehensive build system with automated version management:

#### Version Management (`scripts/generate_version.py`)
- **Dynamic Version Generation**: Based on git tags, commits, and timestamps
- **Build Information**: Captures commit hash, branch, build time, Python version, platform
- **Version Formats**: Both full version (with build info) and short version (tag only)
- **Auto-Generated**: `src/version.py` is automatically created and should not be edited manually

#### Build Scripts
- **`scripts/build.py`**: Full production build with PyInstaller, dependency management, and type checking
- **`scripts/dev_build.py`**: Quick development builds with optional file watching via watchdog
- **Build Artifacts**: Executable, build info JSON, version text, logs directory, settings template

#### Build Configuration
- **`DG-LAB-VRCOSC.spec`**: Optimized PyInstaller configuration with proper resource bundling
- **Dependency Management**: Automatic pip updates and requirement installation
- **Type Safety**: Integrated pyright type checking in build process
- **Cross-Platform**: Windows-optimized with proper console encoding

## Key File Structure

- `src/`: Main source code directory
  - `gui/`: PySide6 GUI components (main_window.py + tab modules)  
  - `services/`: Service layer (dglab_websocket_service.py, dglab_bluetooth_service.py, osc_service.py, chatbox_service.py)
  - `core/`: Core functionality including interfaces, registries, and Bluetooth protocol
    - `bluetooth/`: Complete Bluetooth LE implementation for DG-LAB 3.0 devices
  - `locales/`: Translation files for internationalization (zh.yml, en.yml, ja.yml)
  - `version.py`: Auto-generated version information (DO NOT EDIT)
- `scripts/`: Build and development scripts
  - `build.py`: Production build script
  - `dev_build.py`: Development build with file watching
  - `generate_version.py`: Dynamic version generation
- `.vscode/`: VSCode configuration
  - `tasks.json`: Build and development tasks
  - `launch.json`: Debug configurations
- `docs/`: Documentation assets and images
- `logs/`: Application log files (auto-generated)
- `dist/`: Build output directory (created by build scripts)
- `build/`: Intermediate build files (created by PyInstaller)
- `settings.yml`: User configuration file (auto-generated)
- `requirements.txt`: Python dependencies
- `DG-LAB-VRCOSC.spec`: PyInstaller configuration

## Development Notes

### Core Development Guidelines
- **Service Usage**: Always use service-based architecture - services are managed by ServiceController
- **Interface Implementation**: Use ABC with `@abstractmethod`, never Protocol
- **Abstract Methods**: Use `...` (ellipsis) in abstract method bodies, not `pass`
- **Translation System**: Use `_("translation.key")` with dot-notation for nested keys
- **Language Support**: Add translations to ALL three language files in `src/locales/`
- **QR Code Generation**: Handled in `util.py` for device pairing
- **Logging**: Configured in `logger_config.py` with file + UI output
- **Chinese Parameters**: VRChat integration uses Chinese parameter names by default
- **Async Operations**: Heavy use of asyncio - ensure proper await usage
- **Device Abstraction**: All device services must implement IDGLabDeviceService interface

### Protocol Layer vs Service Layer Guidelines

**Protocol Layer (`src/core/websocket/`, `src/core/bluetooth/`)**:
- **Focus**: Frame-level device communication and protocol implementation
- **Terminology**: Use "frame" terminology (not "playback") for protocol-level operations
- **PlaybackMode**: Use `PlaybackMode` enum for ONCE/LOOP frame sequence modes
- **Key Methods**: `advance_buffer_for_send()`, `advance_logical_frame()`, `is_frame_sequence_finished()`
- **Responsibility**: 100ms time slices, channel state management, device-specific protocol details

**Service Layer (`src/services/`)**:
- **Focus**: High-level business logic and application features  
- **Terminology**: Use "playback" terminology for user-facing recording/playback features
- **Integration**: Services use protocol layer for actual device communication
- **Responsibility**: Recording system, OSC actions, user interface abstractions
- **Abstraction**: Hide protocol details from application logic

### Code Quality Guidelines

**Type Safety**:
- **No Inline Imports**: All imports must be at the top of the file - no inline imports allowed
- **Strict Typing**: Use strict type annotations - avoid `Any` type completely
- **Complex Dictionaries**: Use `TypedDict` for complex dictionary structures instead of `Dict[str, Any]`
- **Complete Type Annotations**: All code must provide complete type annotations including variables, function parameters, return values, class attributes, and method signatures
- **Generic Types**: Use proper generic types like `List[str]`, `Dict[str, int]` instead of bare `list`, `dict`
- **Optional Types**: Use `Optional[T]` or `T | None` for nullable values explicitly
- **TODO Markers**: Use `# TODO:` comments for any placeholder code, unimplemented features, or areas requiring future implementation
- **Type Annotation Quotes**: Only use quotes in type annotations for forward references (e.g., nested classes referencing outer classes)

**Import Management**:
- **No Import Renaming**: Avoid `from module import SomeClass as Alias` - use direct imports instead
- **Direct Imports Preferred**: Use `from module import SomeClass` for normal cases
- **Module Prefix for Conflicts**: Only use `from module import submodule` then `submodule.SomeClass` when there are naming conflicts
- **Name Collision Resolution**: When classes have same names across modules, use module prefixes to distinguish them
- **Example**: Use `websocket_models.PlaybackMode` and `bluetooth_models.PlaybackMode` instead of renaming to `WSPlaybackMode` and `BTPlaybackMode`

**Code Modification Standards**:
- **No Explanatory Comments**: Do not add explanatory comments like "// Fixed callback registration" when modifying code
- **Self-Documenting Code**: Code should be clear from its structure and naming, not from added comments
- **Comment Policy**: Only add comments for complex business logic, not for implementation changes or fixes
- **Clean Commits**: Remove any debugging or explanatory comments before committing

**Forward Reference Guidelines**:
- **Quotes Required**: Use quotes for type annotations when the referenced class is not yet defined
- **Common Cases**: Nested classes referencing outer classes, circular imports, self-referencing classes
- **Current Usage**: Inner handler classes use `'DGLabWebSocketService'` and `'DGLabBluetoothService'` as forward references
- **No `__future__.annotations`**: Project does not use delayed annotation evaluation, so forward references must be quoted
- **Example**: `def __init__(self, service: 'OuterClass') -> None:` in nested classes

**Dynamic Type Features Prohibition**:
- **No Dynamic Attributes**: Avoid `getattr()`, `setattr()`, `hasattr()` for class attributes - declare all attributes explicitly in `__init__`
- **No Dynamic Imports**: Avoid `__import__()`, `importlib` for dynamic module loading
- **No Monkey Patching**: Never modify class or instance attributes at runtime using dynamic assignment
- **Explicit Attribute Declaration**: All class attributes must be declared with proper type annotations in `__init__`
- **Static Analysis Friendly**: Code must be analyzable by static type checkers without dynamic features
- **Example Violation**: `setattr(self, '_dynamic_attr', value)` ❌
- **Correct Pattern**: `self._explicit_attr: Optional[Type] = None` in `__init__` ✅

### Recording System Architecture
The recording system uses a layered architecture:
- **Interface Layer**: `IPulseRecordHandler`, `IPulsePlaybackHandler` using ABC
- **Base Implementation**: `BaseRecordHandler`, `BasePlaybackHandler` with common logic
- **Data Models**: `RecordingSession`, `RecordingSnapshot`, `ChannelSnapshot` for 100ms time slices
- **File Management**: `DGRFileManager` for JSON-based .dgr file serialization
- **Integration**: Recording handlers are called via `on_data_sync()` to synchronize with device data updates

#### BasePlaybackHandler Optimization Guidelines
The `BasePlaybackHandler` has been optimized to eliminate redundancy and improve maintainability:

**Removed Unnecessary Abstractions**:
- Eliminated `_get_total_positions()` - moved logic to base class `get_total_snapshots()`
- Removed `_register_progress_listener()` and `_unregister_progress_listener()` - callbacks now registered directly in child class `__init__`
- Deleted unused methods `_is_currently_playing()` and `_is_currently_paused()` from all implementations

**Unified Callback System**:
- Progress callbacks use consistent `ProgressCallback` type: `(current: int, total: int, percentage: float) -> None`
- Callback registration moved to child class constructors for better control
- Simplified callback management with single callback instances instead of callback lists

**Interface Implementation Pattern**:
- Child classes directly implement interface methods (`get_current_position()`, `get_total_snapshots()`) 
- Base class provides common implementations where possible
- Abstract methods only used for truly implementation-specific functionality

**Code Quality Standards**:
- When removing code blocks, always check for and clean up resulting empty lines
- Maintain consistent spacing and formatting
- Ensure type annotations are consistent across all implementations

### Build System Guidelines
- **Version Management**: Never edit `src/version.py` manually - it's auto-generated
- **Development Workflow**: Use `scripts/dev_build.py --watch` for active development
- **Production Builds**: Use `scripts/build.py` for release builds
- **Type Safety**: All builds include pyright type checking - fix type errors before building
- **Dependencies**: `watchdog` is required for development file watching functionality
- **VSCode Integration**: Use Ctrl+Shift+P → "Tasks: Run Task" for build operations

### Version Information Access
```python
# Import version information in your code
try:
    from version import get_version, get_version_short, get_build_info
    version = get_version()  # Full version with build info
    short_version = get_version_short()  # Tag-only version
    build_info = get_build_info()  # Complete build metadata
except ImportError:
    # Fallback for development without generated version
    version = "v0.0.0-dev"
```

### IDE Configuration
- **Type Checking**: Configure your IDE to use pyright for enhanced type checking
- **Tasks**: VSCode users can access build tasks via Command Palette
- **Debugging**: Use "DG-LAB-VRCOSC" launch configuration for debugging with auto version generation

## Component Initialization Order

**Critical**: OSC actions must be registered AFTER controller is available:

1. `init_ui()` - Initialize GUI components
2. When controller becomes available via `set_controller()`:
   - `load_custom_pulses()` - Load and register custom pulse actions
   - `_register_osc_actions_with_controller()` - Register OSC actions
   - `load_osc_parameter_bindings()` - Bind parameters to actions (must be last)

## Connection and Pulse Synchronization

### Initial Pulse State Management

**Critical**: After successful connection (both WebSocket and Bluetooth), the system must ensure UI pulse state is synchronized with the service layer:

#### Connection Flow
1. **Connection Established**: WebSocket or Bluetooth connection succeeds
2. **Service Controller Created**: ServiceController instance with all services initialized  
3. **UI Controller Registration**: `ui_interface.set_service_controller(service_controller)` called
4. **Pulse State Sync**: `asyncio.create_task(service_controller.osc_action_service.update_pulse())` **MUST** be called

#### Required Implementation Pattern
Both connection managers must include pulse synchronization after successful connection:

```python
# In WebSocketConnectionManager and BluetoothConnectionManager
service_controller = ServiceController(dglab_device_service, osc_service, osc_action_service, chatbox_service)
self.ui_interface.set_service_controller(service_controller)

# CRITICAL: Synchronize initial pulse state
asyncio.create_task(service_controller.osc_action_service.update_pulse())
```

#### Why This Is Required
- **UI State**: Settings tab may show saved pulse configuration
- **Service State**: Newly created services have no pulse data applied
- **Sync Gap**: Without explicit synchronization, UI displays one state while services run with empty/null pulse data
- **Solution**: `update_pulse()` reads current UI pulse selection and applies it to the service layer

#### Common Bug Pattern
**Symptom**: "Connection successful but initial pulse invalid, task not set"

**Root Cause**: Missing `update_pulse()` call after connection establishment

**Fix**: Always call `service_controller.osc_action_service.update_pulse()` after `set_service_controller()`