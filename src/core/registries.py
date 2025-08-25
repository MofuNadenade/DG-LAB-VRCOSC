from core.dglab_pulse import PulseRegistry
from core.osc_action import OSCActionRegistry
from core.osc_address import OSCAddressRegistry
from core.osc_binding import OSCBindingRegistry
from core.osc_template import OSCTemplateRegistry


class Registries:
    def __init__(self) -> None:
        """
        初始化 Registries 实例
        """
        super().__init__()

        self.pulse_registry: PulseRegistry = PulseRegistry()
        self.address_registry: OSCAddressRegistry = OSCAddressRegistry()
        self.action_registry: OSCActionRegistry = OSCActionRegistry()
        self.binding_registry: OSCBindingRegistry = OSCBindingRegistry()
        self.template_registry: OSCTemplateRegistry = OSCTemplateRegistry()
