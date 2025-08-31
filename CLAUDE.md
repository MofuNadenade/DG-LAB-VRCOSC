# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DG-LAB-VRCOSC is a Python desktop application that controls DG-LAB 3.0 devices through VRChat OSC integration and Terrors of Nowhere game events. The application uses a PySide6 GUI with asyncio for handling WebSocket connections to both the DG-LAB hardware and external game integrations.

## Development Commands

### Installation and Setup
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
# Development mode
python src/app.py

# Development mode with file watching and auto-rebuild
python scripts/dev_build.py --watch
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

### Code Quality
The project uses multiple tools for code quality, integrated into the build system:

**Type Checking (mypy):**
```bash
# Run type checking on all typed modules
python -m mypy src/ --ignore-missing-imports
```

**Linting (flake8):**
```bash
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

**Code Formatting (ruff):**
```bash
# Check formatting
python -m ruff check src/

# Auto-fix issues
python -m ruff check --fix src/
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
2. **Main UI** (`src/gui/main_window.py`): PySide6-based main window implementing the UICallback protocol with tabbed interface
3. **Device Controller** (`src/dglab_controller.py`): Pure service container with no methods, only property accessors
4. **Services Architecture** (`src/services/`): Modular service-based architecture with separated concerns
5. **OSC System** (`src/osc_binding.py`): Registry-based OSC parameter and action binding system
6. **Configuration** (`src/config.py`): YAML-based settings management with network interface detection

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

#### Core Services (`src/services/`)
- **DGLabService**: All DG-LAB hardware control (strength, channels, pulses, fire mode)
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

### Interface Architecture

All interfaces use Abstract Base Classes (ABC) with `@abstractmethod` decorators:

- **IService**: Base service interface for lifecycle management
- **IDGLabDeviceService**: Hardware abstraction for different connection types (WebSocket, Bluetooth)
- **CoreInterface**: Core functionality interface for logging, state management
- **UIInterface**: UI operations interface extending CoreInterface

### OSC Parameter System

The application uses a three-layer OSC binding system:
- `OSCAddressRegistry`: Maps parameter names to OSC codes
- `OSCActionRegistry`: Maps action names to callback functions  
- `OSCBindingRegistry`: Binds parameters to actions for event handling

Default parameters include VRChat contact/physbone interactions and SoundPad button controls.

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
- **Terrors of Nowhere**: Integrates with ToNSaveManager WebSocket API for game events (`src/ton_websocket_handler.py`)

### GUI Architecture

The main window (`src/gui/main_window.py`) implements a tabbed interface:
- **NetworkConfigTab**: Network settings and server management
- **ControllerSettingsTab**: Device control and pulse configuration
- **TonDamageSystemTab**: Terrors of Nowhere game integration
- **AboutTab**: Application information, version details, and feedback links
- **LogViewerTab**: Application logging and debugging

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
- **Type Safety**: Integrated mypy type checking in build process
- **Cross-Platform**: Windows-optimized with proper console encoding

## Key File Structure

- `src/`: Main source code directory
  - `gui/`: PySide6 GUI components (main_window.py + tab modules)  
  - `services/`: Service layer (dglab_service.py, osc_service.py, chatbox_service.py)
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

### Build System Guidelines
- **Version Management**: Never edit `src/version.py` manually - it's auto-generated
- **Development Workflow**: Use `scripts/dev_build.py --watch` for active development
- **Production Builds**: Use `scripts/build.py` for release builds
- **Type Safety**: All builds include mypy type checking - fix type errors before building
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
- **Type Checking**: Configure your IDE to use mypy with `--ignore-missing-imports`
- **Tasks**: VSCode users can access build tasks via Command Palette
- **Debugging**: Use "DG-LAB-VRCOSC" launch configuration for debugging with auto version generation

## Component Initialization Order

**Critical**: OSC actions must be registered AFTER controller is available:

1. `init_ui()` - Initialize GUI components
2. When controller becomes available via `set_controller()`:
   - `load_custom_pulses()` - Load and register custom pulse actions
   - `_register_osc_actions_with_controller()` - Register OSC actions
   - `load_osc_parameter_bindings()` - Bind parameters to actions (must be last)