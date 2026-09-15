"""Validated public request models, shared by API and batch workers."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, validate_default=True)


class SatcomInput(RequestModel):
    material: Literal['Si', 'SiGe', 'GaAs', 'GaN', 'SiC']="GaN"
    pa_efficiency_override: float | None = Field(None, ge=0.01, le=0.95)
    part_pa:str="PA-GaN-Ka-20W"
    part_lna:str="LNA-GaAs-Ka"
    altitude_km:float=Field(1280, ge=0.001, le=100000)
    min_elevation_deg:float=Field(20, ge=0, le=90)
    frequency_ghz:float=Field(20, ge=0.001, le=1000)
    bandwidth_mhz:float=Field(100, ge=0.001, le=100000)
    rf_output_w:float=Field(20, ge=0.001, le=100000)
    tx_gain_dbi:float=Field(34, ge=-300, le=300)
    rx_gain_dbi:float=Field(42, ge=-300, le=300)
    losses_db:float=Field(3, ge=-300, le=300)
    antenna_temp_k:float=Field(290, ge=0, le=1e9)
    bus_power_w:float=Field(1800, gt=0, le=1e9)
    payload_share:float=Field(.5, gt=0, le=1)
    antenna_diameter_m:float=Field(.45, ge=0.001, le=1000)
    antenna_efficiency:float=Field(.62, gt=0, le=1)
    structure_mass_kg:float=Field(180, ge=0, le=1e9)
    base_payload_mass_kg:float=Field(75, ge=0, le=1e9)
    base_cost_musd:float=Field(12, ge=0, le=1e9)
    radiator_w_m2:float=Field(350, ge=0, le=1e9)
    mission_years:float=Field(5, gt=0, le=100)
    array_elements:int=Field(256, ge=1, le=4096)
    beams:int=Field(8, ge=1, le=128)
    processor: Literal['FPGA', 'ASIC']="FPGA"
    processor_tops:float=Field(1.5, ge=0.001, le=10000)
    coding_gap_db:float=Field(2.0, ge=-300, le=300)
    max_spectral_eff:float=Field(6.0, ge=0, le=1e9)
    atmospheric_loss_db:float=Field(0.0, ge=-300, le=300)
    radiator_temp_k:float=Field(323.15, gt=3, le=5000)
    radiator_emissivity:float=Field(0.85, gt=0, le=1)
    radiator_view_factor:float=Field(0.80, gt=0, le=1)


class BeamInput(RequestModel):
    elements:int=Field(256, ge=1, le=4096)
    beams:int=Field(8, ge=1, le=128)
    bandwidth_mhz:float=Field(100, ge=0.001, le=100000)
    sample_gsps:float=Field(1.0, ge=0.001, le=1000)
    bits:int=Field(12, ge=1, le=32)
    architecture: Literal["Analog", "Hybrid", "Fully Digital"] = "Fully Digital"
    processor: Literal['FPGA', 'ASIC']="FPGA"
    available_tops:float=Field(2.0, ge=0, le=10000)
    available_power_w:float=Field(180, ge=0, le=1e9)
    phase_bits:int=Field(6, ge=1, le=32)
    amplitude_bits:int=Field(6, ge=1, le=32)
    calibration_error_deg:float=Field(2.0, ge=0, le=1e9)
    element_spacing_lambda:float=Field(.5, gt=0, le=10)
    max_scan_deg:float=Field(60.0, ge=0, le=90)


class RadInput(RequestModel):
    mission_years:float=Field(5, gt=0, le=100)
    shielding_mm_al:float=Field(2, ge=0, le=1000)
    tid_env_krad_yr:float=Field(2, ge=0, le=1e9)
    tid_tolerance_krad:float=Field(30, gt=0, le=1e9)
    dd_env_arb_yr:float=Field(1, ge=0, le=1e9)
    dd_tolerance_arb:float=Field(10, gt=0, le=1e9)
    seu_rate_device_day:float=Field(.002, ge=0, le=1e9)
    sel_rate_device_day:float=Field(.00002, ge=0, le=1e9)
    sensitive_devices:int=Field(25, ge=1, le=100000)
    mitigation: Literal['None', 'ECC', 'TMR', 'TMR+Scrub']="TMR+Scrub"
    scrub_interval_min:float=Field(10, ge=0, le=1e9)
    spares:int=Field(1, ge=0, le=10000)
    reset_recovery_sec:float=Field(5, ge=0, le=1e9)
    service_nodes:int=Field(128, ge=1, le=100000)


class PayloadInput(RequestModel):
    architecture: Literal["Bent-Pipe", "Regenerative", "Flexible Digital"] = "Regenerative"
    frequency_ghz:float=Field(20, ge=0.001, le=1000)
    bandwidth_mhz:float=Field(500, ge=0.001, le=100000)
    input_power_dbw:float=Field(-115, ge=-300, le=300)
    antenna_gain_rx_dbi:float=Field(35, ge=-300, le=300)
    antenna_gain_tx_dbi:float=Field(35, ge=-300, le=300)
    lna_gain_db:float=Field(30, ge=-300, le=300)
    lna_nf_db:float=Field(1.3, ge=-300, le=300)
    filter_loss_db:float=Field(1.0, ge=-300, le=300)
    mixer_loss_db:float=Field(6.0, ge=-300, le=300)
    channelizer_loss_db:float=Field(1.5, ge=-300, le=300)
    switch_loss_db:float=Field(1.0, ge=-300, le=300)
    pa_gain_db:float=Field(28, ge=-300, le=300)
    pa_output_w:float=Field(20, ge=0.001, le=100000)
    pa_efficiency:float=Field(.46, gt=0, le=1)
    channels:int=Field(16, ge=1, le=256)
    beams:int=Field(8, ge=0, le=128)
    processor_power_w:float=Field(120, ge=0, le=1e9)
    converter_power_w:float=Field(55, ge=0, le=1e9)
    other_power_w:float=Field(90, ge=0, le=1e9)
    dry_mass_kg:float=Field(65, ge=0, le=1e9)
    thermal_margin_pct:float=Field(20, ge=0, le=1e9)
    radiator_temp_k:float=Field(323.15, gt=3, le=5000)
    radiator_emissivity:float=Field(0.85, gt=0, le=1)
    radiator_view_factor:float=Field(0.80, gt=0, le=1)
    papr_db:float=Field(8.0, ge=0, le=60)
    output_backoff_db:float=Field(3.0, ge=0, le=60)
    hpa_model:str="Rapp"
    rapp_p:float=Field(3.0, gt=0, le=20)
    dpd_enabled:bool=True
    dpd_gain_db:float=Field(2.0, ge=0, le=60)
    frequency_reuse:int=Field(4, ge=1, le=128)
    beam_hopping_duty:float=Field(0.50, gt=0, le=1)
    traffic_hotspot_factor:float=Field(2.0, gt=0, le=100)
    precoding_enabled:bool=False
    precoding_efficiency:float=Field(0.80, ge=0, le=1)
    channelizer_granularity_mhz:float=Field(5.0, ge=0.001, le=100000)
    routing_matrix_inputs:int=Field(8, ge=1, le=128)
    routing_matrix_outputs:int=Field(8, ge=1, le=128)
    regenerative_stack: Literal['PHY', 'PHY+MAC', 'gNB-DU', 'gNB Full']="PHY"
    isl_offload_fraction:float=Field(0.0, ge=0, le=1)
    # V1.1 interference / traffic / waveform
    users:int=Field(16, ge=1, le=128)
    user_noise_dbm:float=Field(-100.0, ge=-300, le=300)
    desired_signal_dbm:float=Field(-80.0, ge=-300, le=300)
    cochannel_coupling_db:float=Field(-18.0, ge=-300, le=300)
    precoding_method: Literal['MRT', 'ZF', 'RZF']="RZF"
    rzf_lambda:float=Field(0.1, ge=0, le=1e9)
    traffic_pattern: Literal['Uniform', 'Hotspot', 'Edge-heavy']="Hotspot"
    scheduler: Literal['Round Robin', 'Max C/I', 'Proportional Fair']="Proportional Fair"
    timeslots:int=Field(16, ge=1, le=128)
    hpa_samples:int=Field(2048, ge=64, le=32768)
    modulation_order: Literal[4, 16, 64, 256] = 16
    aclr_guard_fraction:float=Field(0.15, gt=0, lt=0.5)
    # V1.2 geometry-resolved channel
    geometry_channel_enabled:bool=True
    geometry_region: Literal['Korea', 'UAE', 'Southeast Asia']="Korea"
    geometry_time_min:float=Field(0.0, ge=0, le=10080)
    geometry_user_radius_km:float=Field(250.0, ge=0, le=20000)
    geometry_satellite_count:int=Field(1, ge=1, le=60)
    geometry_inclination_deg:float=Field(42.0, ge=0, le=180)
    geometry_planes:int=Field(16, ge=1, le=60)
    geometry_sats_per_plane:int=Field(8, ge=1, le=60)
    geometry_walker_f:int=Field(1, ge=0, le=59)
    geometry_altitude_km:float=Field(1280.0, ge=0.001, le=100000)
    geometry_min_elevation_deg:float=Field(10.0, ge=0, le=90)
    geometry_terminal_gain_dbi:float=Field(32.0, ge=-300, le=300)
    geometry_beam_hpbw_deg:float=Field(2.5, gt=0, le=180)
    geometry_atmospheric_loss_db:float=Field(1.0, ge=-300, le=300)
    geometry_total_tx_power_w:float=Field(40.0, ge=0, le=100000)
    analysis_mode: Literal['Full', 'Fast']="Full"


class PropagationInput(RequestModel):
    frequency_ghz: float = Field(20.0, ge=0.001, le=1000)
    elevation_deg: float = Field(30.0, gt=0, le=90)
    rain_rate_mm_h: float = Field(25.0, ge=0, le=1e9)
    polarization: str = "Circular"
    polarization_tilt_deg: float = Field(45.0, ge=0, le=180)
    rain_height_km: float = Field(5.0, ge=0, le=1e9)
    station_height_km: float = Field(0.1, ge=0, le=1e9)
    path_reduction_factor: float = Field(1.0, gt=0, le=1)


class PassTimelineInput(RequestModel):
    altitude_km: float = Field(1280, ge=0.001, le=100000)
    inclination_deg: float = Field(42, ge=0, le=180)
    planes: int = Field(16, ge=1, le=60)
    sats_per_plane: int = Field(8, ge=1, le=60)
    walker_f: int = Field(1, ge=0, le=59)
    region: Literal['Korea', 'UAE', 'Southeast Asia'] = "Korea"
    min_elevation_deg: float = Field(20, ge=0, le=90)
    duration_hours: float = Field(6, ge=0.01, le=72)
    time_step_sec: float = Field(60, ge=5, le=3600)

    @model_validator(mode="after")
    def bounded_work(self):
        samples = int(min(self.duration_hours, 48) * 3600 / max(10, min(900, self.time_step_sec))) + 2
        if samples * self.planes * self.sats_per_plane > 2000000:
            raise ValueError("Requested orbit sampling exceeds the work budget; reduce duration/satellites or increase time step")
        return self


class PoissonDeviceInput(RequestModel):
    thickness_um: float = Field(1.0, ge=0.001, le=10000)
    net_doping_cm3: float = Field(1e15, ge=-1e22, le=1e22)
    relative_permittivity: float = Field(11.7, ge=0.001, le=1000)
    left_potential_v: float = Field(0.0, ge=-1000, le=1000)
    right_potential_v: float = Field(0.5, ge=-1000, le=1000)
    grid_points: int = Field(121, ge=3, le=401)
    model: str = "Depletion"
    temperature_k: float = Field(300.0, gt=0, le=5000)
    intrinsic_cm3: float = Field(1.0e10, gt=0, le=1e22)
    carrier_sign: Literal[-1, 1] = 1
    max_iterations: int = Field(80, ge=1, le=200)
    tolerance_v: float = Field(1e-7, gt=0, le=1)


class IntegratedInput(RequestModel):
    satcom: SatcomInput = Field(default_factory=SatcomInput)
    beam: BeamInput = Field(default_factory=BeamInput)
    radiation: RadInput = Field(default_factory=RadInput)
    payload: PayloadInput = Field(default_factory=PayloadInput)


class OptimizeInput(RequestModel):
    base: IntegratedInput = Field(default_factory=IntegratedInput)
    max_total_mass_kg: float = Field(500, ge=0, le=1e9)
    max_payload_power_w: float = Field(1200, ge=0, le=1e9)
    min_effective_capacity_gbps: float = Field(2.0, ge=0, le=1e9)
    min_effective_beams: int = Field(4, ge=0, le=128)
    min_availability_pct: float = Field(99.9, ge=0, le=100)
    max_cost_musd: float = Field(100, ge=0, le=1e9)
    allowed_risk: Literal['LOW', 'MEDIUM', 'HIGH'] = "MEDIUM"
    objective: Literal['Balanced', 'Lowest Cost', 'Highest Capacity', 'Lowest Mass'] = "Balanced"

    @model_validator(mode="after")
    def bounded_batch(self):
        if self.base.payload.users ** 3 * self.base.payload.timeslots * 1728 > 500_000_000:
            raise ValueError("Batch workload is too large; reduce users, time slots, or run count")
        return self


class SensitivityInput(RequestModel):
    base: IntegratedInput = Field(default_factory=IntegratedInput)
    parameter: Literal['rf_output_w', 'bandwidth_mhz', 'beams', 'elements', 'altitude_km', 'shielding_mm_al'] = "rf_output_w"
    low: float = 10
    high: float = 40
    steps: int = Field(7, ge=3, le=25)

    @model_validator(mode="after")
    def valid_range(self):
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        name = "array_elements" if self.parameter == "elements" else self.parameter
        base = self.base.radiation if name == "shielding_mm_al" else self.base.satcom
        for value in (self.low, self.high):
            if name in ("beams", "array_elements"):
                value = int(round(value))
            type(base).model_validate({**base.model_dump(), name: value})
        return self


class CoverageInput(RequestModel):
    altitude_km: float = Field(1280, ge=0.001, le=100000)
    inclination_deg: float = Field(42, ge=0, le=180)
    planes: int = Field(16, ge=1, le=60)
    sats_per_plane: int = Field(8, ge=1, le=60)
    min_elevation_deg: float = Field(20, ge=0, le=90)
    target_min_visible: int = Field(1, ge=1, le=3600)
    walker_f: int = Field(1, ge=0, le=59)
    duration_hours: float = Field(24, ge=0.01, le=168)
    time_step_sec: float = Field(120, ge=5, le=3600)

    @model_validator(mode="after")
    def bounded_work(self):
        samples = int(min(self.duration_hours, 168) * 3600 / max(20, min(1800, self.time_step_sec))) + 2
        if samples * self.planes * self.sats_per_plane > 10000000:
            raise ValueError("Requested orbit sampling exceeds the work budget; reduce duration/satellites or increase time step")
        return self


class MonteCarloInput(RequestModel):
    base: IntegratedInput = Field(default_factory=IntegratedInput)
    runs: int = Field(500, ge=1, le=5000)
    seed: int = Field(42, ge=0, le=4294967295)
    rf_output_sigma_pct: float = Field(5, ge=0, le=100)
    pa_eff_sigma_pct: float = Field(6, ge=0, le=100)
    loss_sigma_db: float = Field(0.8, ge=0, le=100)
    bandwidth_sigma_pct: float = Field(5, ge=0, le=100)
    processor_tops_sigma_pct: float = Field(8, ge=0, le=100)
    tid_sigma_pct: float = Field(20, ge=0, le=100)
    seu_sigma_pct: float = Field(25, ge=0, le=100)
    mass_sigma_pct: float = Field(4, ge=0, le=100)
    cost_sigma_pct: float = Field(8, ge=0, le=100)
    capacity_threshold_gbps: float = Field(2.0, ge=0, le=1e9)
    max_power_w: float = Field(1200, ge=0, le=1e9)
    max_mass_kg: float = Field(500, ge=0, le=1e9)

    @model_validator(mode="after")
    def bounded_batch(self):
        if self.base.payload.users ** 3 * self.base.payload.timeslots * self.runs > 500_000_000:
            raise ValueError("Batch workload is too large; reduce users, time slots, or run count")
        return self
