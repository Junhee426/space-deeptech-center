def optimize_case_worker(arg):
    from core import engine as core
    base=core.IntegratedInput.model_validate(arg["base"])
    c=arg["candidate"]
    proc=c["processor"]; mat=c["material"]
    sat=base.satcom.model_copy(update={
        "material":mat,
        "part_pa":"PA-GaN-Ka-20W" if mat=="GaN" else "PA-GaAs-Ka-10W",
        "altitude_km":c["altitude_km"],
        "beams":c["beams"],
        "rf_output_w":c["rf_output_w"],
        "array_elements":c["elements"],
        "bandwidth_mhz":c["bandwidth_mhz"],
        "processor":proc,
        "processor_tops":5.0 if proc=="ASIC" else 2.0,
    })
    beam=base.beam.model_copy(update={
        "architecture":"Fully Digital" if proc=="ASIC" else "Hybrid",
        "processor":proc,
        "beams":c["beams"],
        "elements":c["elements"],
        "bandwidth_mhz":c["bandwidth_mhz"],
        "available_tops":5.0 if proc=="ASIC" else 2.0,
        "available_power_w":220 if proc=="ASIC" else 180,
    })
    payload=base.payload.model_copy(update={
        "analysis_mode":"Fast","hpa_samples":256,"geometry_channel_enabled":False
    })
    r=core.integrated_calc(core.IntegratedInput(
        satcom=sat,beam=beam,radiation=base.radiation,payload=payload
    ))["integrated"]
    return {**c,**r}

def monte_carlo_case_worker(arg):
    from core import engine as core
    base=core.IntegratedInput.model_validate(arg["base"])
    d=arg["draw"]
    sat=base.satcom.model_copy(update={
        "rf_output_w":d["rf"],"bandwidth_mhz":d["bw"],
        "losses_db":d["loss"],"processor_tops":d["tops"]
    })
    beam=base.beam.model_copy(update={"bandwidth_mhz":d["bw"],"available_tops":d["tops"]})
    rad=base.radiation.model_copy(update={"tid_env_krad_yr":d["tid"],"seu_rate_device_day":d["seu"]})
    payload=base.payload.model_copy(update={
        "bandwidth_mhz":d["bw"],"analysis_mode":"Fast",
        "hpa_samples":256,"geometry_channel_enabled":False
    })
    r=core.integrated_calc(core.IntegratedInput(
        satcom=sat,beam=beam,radiation=rad,payload=payload
    ))["integrated"]
    mass=max(.1,r["total_mass_kg"]*d["mass_factor"])
    cost=max(.01,r["total_cost_proxy_musd"]*d["cost_factor"])
    return {
        "capacity_gbps":r["effective_capacity_gbps"],
        "power_w":r["payload_power_w"],
        "mass_kg":mass,
        "cost_musd":cost
    }
