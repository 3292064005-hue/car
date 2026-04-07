from robot_contracts.faults import fault_definition, recoverable_fault_codes


def test_fault_dictionary_contains_uart_and_watchdog() -> None:
    assert fault_definition('UART_FAULT') is not None
    assert fault_definition('WATCHDOG_FAULT') is not None
    assert 'LOW_BAT_WARN' in recoverable_fault_codes()
