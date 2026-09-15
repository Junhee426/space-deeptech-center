from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from enum import Enum
from math import log10, log2, sqrt, cos, acos, sin, radians, degrees, pi
from io import StringIO
import csv
import math
import random
from statistics import mean
import numpy as np
from functools import lru_cache

from simulation.batch import batched_design_grid, parallel_map, monte_carlo_draws
from simulation.workers import optimize_case_worker, monte_carlo_case_worker
from orbit.walker import walker_positions_times, regional_visibility_times

# Physics core constants (SI unless noted)
R_EARTH = 6371.0              # mean spherical Earth radius [km]
MU_EARTH = 398600.4418        # Earth GM [km^3/s^2]
OMEGA_EARTH = 7.2921159e-5    # sidereal rotation [rad/s]
C_LIGHT = 299792458.0         # [m/s]
K_BOLTZ = 1.380649e-23        # [J/K]
SIGMA_SB = 5.670374419e-8     # Stefan-Boltzmann [W/m^2/K^4]
T_SPACE = 3.0                 # deep-space sink approximation [K]
K_DBW = 10*log10(K_BOLTZ)     # about -228.6 dBW/K/Hz

MATERIALS = {
    "Si":{"name":"Silicon","pa_eff":0.28,"lna_nf":2.2,"thermal":0.70,"rad":0.55,"cost":1.0,"maturity":0.98,"freq":20,"density":2.33},
    "SiGe":{"name":"SiGe","pa_eff":0.34,"lna_nf":1.6,"thermal":0.74,"rad":0.62,"cost":1.35,"maturity":0.91,"freq":80,"density":2.8},
    "GaAs":{"name":"Gallium Arsenide","pa_eff":0.39,"lna_nf":1.25,"thermal":0.68,"rad":0.70,"cost":1.8,"maturity":0.94,"freq":100,"density":5.32},
    "GaN":{"name":"Gallium Nitride","pa_eff":0.49,"lna_nf":1.45,"thermal":0.86,"rad":0.77,"cost":2.3,"maturity":0.84,"freq":80,"density":6.15},
    "SiC":{"name":"Silicon Carbide","pa_eff":0.44,"lna_nf":2.0,"thermal":0.95,"rad":0.82,"cost":2.1,"maturity":0.86,"freq":30,"density":3.21},
}

PARTS = {
    "PA-GaN-Ka-20W":{"type":"PA","tech":"GaN","band":"Ka","rf_w":20,"eff":0.46,"gain_db":26,"mass_g":180,"cost_kusd":18},
    "PA-GaAs-Ka-10W":{"type":"PA","tech":"GaAs","band":"Ka","rf_w":10,"eff":0.36,"gain_db":27,"mass_g":160,"cost_kusd":14},
    "PA-GaN-Ka-50W":{"type":"PA","tech":"GaN","band":"Ka","rf_w":50,"eff":0.43,"gain_db":24,"mass_g":320,"cost_kusd":32},
    "LNA-GaAs-Ka":{"type":"LNA","tech":"GaAs","band":"Ka","nf_db":1.2,"gain_db":30,"power_w":2.0,"mass_g":80,"cost_kusd":7},
    "LNA-SiGe-Ka":{"type":"LNA","tech":"SiGe","band":"Ka","nf_db":1.5,"gain_db":27,"power_w":1.4,"mass_g":65,"cost_kusd":5},
    "ADC-12b-2GSPS":{"type":"ADC","bits":12,"gsps":2.0,"power_w":14,"mass_g":45,"cost_kusd":4},
    "ADC-14b-1GSPS":{"type":"ADC","bits":14,"gsps":1.0,"power_w":12,"mass_g":45,"cost_kusd":5},
    "FPGA-Space-Mid":{"type":"FPGA","tops":1.5,"power_w":42,"mass_g":110,"cost_kusd":22},
    "ASIC-DBF-5T":{"type":"ASIC","tops":5.0,"power_w":24,"mass_g":70,"cost_kusd":10},
}

ORBIT_PRESETS = {"500":500,"888":888,"1280":1280}

def db_to_lin(x): return 10**(x/10)
def lin_to_db(x): return 10*log10(max(x,1e-18))
def dbw(w): return 10*log10(max(w,1e-18))

def slant_range(alt,elev):
    e=radians(elev); return sqrt((R_EARTH+alt)**2-(R_EARTH*cos(e))**2)-R_EARTH*sin(e)

def footprint(alt,elev):
    e=radians(elev)
    val=max(-1,min(1,(R_EARTH/(R_EARTH+alt))*cos(e)))
    psi=max(0,acos(val)-e)
    radius=R_EARTH*psi
    area=2*pi*R_EARTH**2*(1-cos(psi))
    return degrees(psi),radius,area

def fspl(freq_ghz,dist_km): return 92.45+20*log10(freq_ghz)+20*log10(dist_km)



@lru_cache(maxsize=2048)
def _cached_slant_range(altitude_km, elevation_deg):
    return slant_range(float(altitude_km), float(elevation_deg))

@lru_cache(maxsize=2048)
def _cached_footprint(altitude_km, elevation_deg):
    return footprint(float(altitude_km), float(elevation_deg))

@lru_cache(maxsize=2048)
def _cached_fspl(freq_ghz, dist_km):
    return fspl(float(freq_ghz), float(dist_km))

@lru_cache(maxsize=2048)
def _cached_orbit_scalar(altitude_km):
    alt=float(altitude_km)
    return orbital_period_s(alt), orbital_speed_km_s(alt)

@lru_cache(maxsize=512)
def _cached_antenna_gain(diameter_m, efficiency, frequency_ghz):
    return antenna_gain_dbi(float(diameter_m), float(efficiency), float(frequency_ghz))

def orbital_period_s(altitude_km: float) -> float:
    a = R_EARTH + altitude_km
    return 2*pi*sqrt(a**3/MU_EARTH)

def orbital_speed_km_s(altitude_km: float) -> float:
    a = R_EARTH + altitude_km
    return sqrt(MU_EARTH/a)

def antenna_gain_dbi(diameter_m: float, efficiency: float, frequency_ghz: float) -> float:
    lam = C_LIGHT/(frequency_ghz*1e9)
    g = max(1e-15, efficiency*(pi*diameter_m/lam)**2)
    return lin_to_db(g)

def noise_temp_from_nf_db(nf_db: float, t0_k: float = 290.0) -> float:
    return t0_k*(db_to_lin(nf_db)-1.0)

def thermal_radiator_area(heat_w: float, temp_k: float, emissivity: float, view_factor: float, margin_pct: float = 0.0) -> float:
    eps=max(0.01,min(1.0,emissivity))
    vf=max(0.01,min(1.0,view_factor))
    net_flux=eps*SIGMA_SB*vf*max(1.0,temp_k**4-T_SPACE**4)
    return max(0.0, heat_w*(1.0+margin_pct/100.0)/net_flux)

def practical_spectral_efficiency(snr_db: float, gap_db: float, max_eff: float) -> float:
    # Shannon-like achievable-rate model with implementation/coding gap Γ.
    gamma = db_to_lin(snr_db)
    gap = db_to_lin(gap_db)
    return max(0.0,min(max_eff,log2(1.0+gamma/max(gap,1e-12))))

def max_orbital_doppler_hz(freq_ghz: float, altitude_km: float) -> float:
    # Upper geometric bound using orbital speed as radial speed.
    return freq_ghz*1e9*(orbital_speed_km_s(altitude_km)*1000.0/C_LIGHT)

def friis_received_power_dbw(pt_w: float, gt_dbi: float, gr_dbi: float, freq_ghz: float, range_km: float, losses_db: float) -> float:
    return dbw(pt_w)+gt_dbi+gr_dbi-fspl(freq_ghz,range_km)-losses_db



# ITU-R P.838-3 Table 5 samples (selected frequencies) used for interpolation.
# Columns: f_GHz, kH, alphaH, kV, alphaV
P838_TABLE = [
    (10,0.01217,1.2571,0.01129,1.2156),
    (15,0.04481,1.1233,0.05008,1.0440),
    (20,0.09164,1.0568,0.09611,0.9847),
    (25,0.1571,0.9991,0.1533,0.9491),
    (30,0.2403,0.9485,0.2291,0.9129),
    (35,0.3374,0.9047,0.3224,0.8761),
    (40,0.4431,0.8673,0.4274,0.8421),
    (45,0.5521,0.8355,0.5375,0.8123),
]

def _interp_p838(f_ghz):
    f=max(P838_TABLE[0][0],min(P838_TABLE[-1][0],f_ghz))
    for a,b in zip(P838_TABLE[:-1],P838_TABLE[1:]):
        if a[0] <= f <= b[0]:
            t=(f-a[0])/(b[0]-a[0])
            return tuple(a[j]+t*(b[j]-a[j]) for j in range(1,5))
    return P838_TABLE[-1][1:]

def rain_specific_attenuation_p838(f_ghz, rain_rate, elevation_deg, pol, tilt_deg):
    kH,aH,kV,aV=_interp_p838(f_ghz)
    theta=radians(elevation_deg)
    if pol.lower().startswith("c"):
        tau=radians(45.0)
    elif pol.lower().startswith("v"):
        tau=radians(90.0)
    elif pol.lower().startswith("h"):
        tau=radians(0.0)
    else:
        tau=radians(tilt_deg)
    cterm=(cos(theta)**2)*cos(2*tau)
    k=(kH+kV+(kH-kV)*cterm)/2
    alpha=(kH*aH+kV*aV+(kH*aH-kV*aV)*cterm)/(2*max(k,1e-15))
    gamma=k*(max(rain_rate,0.0)**alpha)
    return k,alpha,gamma

def geometric_rain_path_km(elevation_deg, rain_height_km, station_height_km):
    dh=max(0.0,rain_height_km-station_height_km)
    s=max(0.05,sin(radians(max(0.1,elevation_deg))))
    return dh/s


def solve_poisson_boltzmann_1d(x):
    q=1.602176634e-19
    eps0=8.8541878128e-12
    kb=1.380649e-23
    eps=eps0*max(1e-6,x.relative_permittivity)
    T=max(50.0,x.temperature_k)
    Vt=kb*T/q
    L=max(1e-9,x.thickness_um*1e-6)
    npts=max(21,min(401,x.grid_points))
    dx=L/(npts-1)
    ni=max(1.0,x.intrinsic_cm3)*1e6
    Ndop=x.carrier_sign*x.net_doping_cm3*1e6
    phi=[x.left_potential_v+(x.right_potential_v-x.left_potential_v)*i/(npts-1) for i in range(npts)]
    m=npts-2
    converged=False
    last_update=0.0

    def thomas(a,b,c,d):
        n=len(b)
        if not n:return []
        cp=[0.0]*max(0,n-1); dp=[0.0]*n
        if n>1: cp[0]=c[0]/b[0]
        dp[0]=d[0]/b[0]
        for i in range(1,n):
            den=b[i]-a[i-1]*(cp[i-1] if i-1<len(cp) else 0.0)
            if abs(den)<1e-20: den=1e-20 if den>=0 else -1e-20
            if i<n-1: cp[i]=c[i]/den
            dp[i]=(d[i]-a[i-1]*dp[i-1])/den
        out=[0.0]*n; out[-1]=dp[-1]
        for i in range(n-2,-1,-1): out[i]=dp[i]-cp[i]*out[i+1]
        return out

    iterations=0
    for iterations in range(1,max(2,min(200,x.max_iterations))+1):
        a=[]; b=[]; c=[]; rhs=[]
        for j in range(1,npts-1):
            ph=max(-1.5,min(1.5,phi[j]))
            n=ni*math.exp(ph/Vt); p=ni*math.exp(-ph/Vt)
            rho=q*(Ndop+p-n)
            drho=q*((-p/Vt)-(n/Vt))
            residual=(phi[j-1]-2*phi[j]+phi[j+1])/(dx*dx)+rho/eps
            jac=-2/(dx*dx)+drho/eps
            if j>1:a.append(1/(dx*dx))
            b.append(jac)
            if j<npts-2:c.append(1/(dx*dx))
            rhs.append(-residual)
        delta=thomas(a,b,c,rhs)
        damp=.25
        last_update=(max(abs(v) for v in delta) if delta else 0.0)*damp
        for j,dv in enumerate(delta,start=1):
            phi[j]=max(-2.0,min(2.0,phi[j]+damp*dv))
        if last_update<x.tolerance_v:
            converged=True
            break

    xpos=[i*dx for i in range(npts)]
    E=[]; charge=[]; electron=[]; hole=[]
    for i,ph0 in enumerate(phi):
        ph=max(-1.5,min(1.5,ph0))
        n=ni*math.exp(ph/Vt); p=ni*math.exp(-ph/Vt)
        charge.append(q*(Ndop+p-n)); electron.append(n/1e6); hole.append(p/1e6)
        if i==0: der=(phi[1]-phi[0])/dx
        elif i==npts-1: der=(phi[-1]-phi[-2])/dx
        else: der=(phi[i+1]-phi[i-1])/(2*dx)
        E.append(-der)
    return {
        "x_um":[round(v*1e6,6) for v in xpos],
        "potential_v":[round(v,9) for v in phi],
        "electric_field_v_m":[round(v,3) for v in E],
        "charge_c_m3":[round(v,8) for v in charge],
        "electron_cm3":[round(v,3) for v in electron],
        "hole_cm3":[round(v,3) for v in hole],
        "max_field_v_m":max(abs(v) for v in E),
        "converged":converged,"iterations":iterations,"last_update_v":last_update,
        "thermal_voltage_v":Vt,
        "physics":"Self-consistent 1-D Poisson-Boltzmann: d²phi/dx²=-q(Ndop+p-n)/eps.",
        "boundary":"Equilibrium Boltzmann carriers; continuity, mobility, recombination and quantum confinement are not included."
    }



def _latlon_to_ecef_np(lat_deg, lon_deg, radius_km=R_EARTH):
    lat=np.radians(np.asarray(lat_deg,dtype=float))
    lon=np.radians(np.asarray(lon_deg,dtype=float))
    cl=np.cos(lat)
    return np.stack([radius_km*cl*np.cos(lon), radius_km*cl*np.sin(lon), radius_km*np.sin(lat)],axis=-1)

def _region_user_grid(region, users, radius_km):
    """
    Deterministic user population around a regional anchor.
    Uses a quasi-uniform golden-angle disk, preserving real regional center coordinates.
    """
    reg=REGIONS.get(region,REGIONS["Korea"])
    users=max(1,min(64,int(users)))
    r=max(1.0,float(radius_km))
    lat0=math.radians(reg["lat_deg"])
    lon0=math.radians(reg["lon_deg"])
    pts=[]
    golden=math.pi*(3-math.sqrt(5))
    for i in range(users):
        rr=r*math.sqrt((i+0.5)/users)
        bearing=i*golden
        d=rr/R_EARTH
        lat=math.asin(math.sin(lat0)*math.cos(d)+math.cos(lat0)*math.sin(d)*math.cos(bearing))
        lon=lon0+math.atan2(math.sin(bearing)*math.sin(d)*math.cos(lat0),
                           math.cos(d)-math.sin(lat0)*math.sin(lat))
        pts.append((math.degrees(lat),((math.degrees(lon)+180)%360)-180))
    return pts

@lru_cache(maxsize=256)
def _walker_ecef_cached(altitude_km, inclination_deg, planes, sats_per_plane, walker_f, t_bucket_s):
    cov=CoverageInput(
        altitude_km=float(altitude_km),inclination_deg=float(inclination_deg),
        planes=int(planes),sats_per_plane=int(sats_per_plane),walker_f=int(walker_f),
        min_elevation_deg=0,target_min_visible=1,duration_hours=1,time_step_sec=60
    )
    return tuple(_walker_satellite_positions_ecef(cov,float(t_bucket_s)))

def _visible_satellites_np(region, altitude_km, inclination_deg, planes, sats_per_plane, walker_f, time_min, min_elev_deg):
    reg=REGIONS.get(region,REGIONS["Korea"])
    ground=np.asarray(_ground_ecef(reg["lat_deg"],reg["lon_deg"])[0],dtype=float)
    zenith=ground/np.linalg.norm(ground)
    # quantize cached state to 1 sec
    t_s=int(round(time_min*60.0))
    sats=np.asarray(_walker_ecef_cached(round(altitude_km,6),round(inclination_deg,6),int(planes),int(sats_per_plane),int(walker_f),t_s),dtype=float)
    los=sats-ground[None,:]
    rng=np.linalg.norm(los,axis=1)
    sinel=(los@zenith)/np.maximum(rng,1e-12)
    elev=np.degrees(np.arcsin(np.clip(sinel,-1,1)))
    idx=np.where(elev>=min_elev_deg)[0]
    return sats,idx,elev,rng

def _gaussian_beam_gain_linear(theta_deg, peak_gain_dbi, hpbw_deg):
    """
    Gaussian main-lobe approximation: power is -3 dB at theta = HPBW/2.
    G(theta)/G0 = exp(-4 ln2 (theta/HPBW)^2)
    """
    h=max(0.05,float(hpbw_deg))
    th=np.asarray(theta_deg,dtype=float)
    rel=np.exp(-4*np.log(2)*(th/h)**2)
    return db_to_lin(peak_gain_dbi)*rel

def _offaxis_angle_deg(sat_xyz, target_xyz, beam_center_xyz):
    a=target_xyz-sat_xyz
    b=beam_center_xyz-sat_xyz
    an=np.linalg.norm(a,axis=-1)
    bn=np.linalg.norm(b,axis=-1)
    dot=np.sum(a*b,axis=-1)/(np.maximum(an*bn,1e-18))
    return np.degrees(np.arccos(np.clip(dot,-1,1)))

def _user_elevation_deg_np(sat_xyz, user_xyz):
    """
    Elevation angle(s) at which each user observes a single satellite above its
    local horizon: the angle between the user->satellite line of sight and the
    user's local zenith direction. This must be measured along the user->satellite
    vector (sat_xyz - user_xyz); using the reversed satellite->user vector flips
    the sign of every result (e.g. a satellite directly overhead would read as
    -90 deg instead of the correct +90 deg).
    Returns (elevation_deg, slant_range_km), both shape (n_users,).
    """
    sat_xyz=np.asarray(sat_xyz,dtype=float)
    user_xyz=np.asarray(user_xyz,dtype=float)
    los=sat_xyz[None,:]-user_xyz
    ranges=np.linalg.norm(los,axis=1)
    ground_norm=user_xyz/np.linalg.norm(user_xyz,axis=1)[:,None]
    elev=np.degrees(np.arcsin(np.clip(np.sum(los*ground_norm,axis=1)/np.maximum(ranges,1e-12),-1,1)))
    return elev,ranges

def _geometry_channel_matrix(x):
    """
    Builds a complex H[user,beam] from actual Walker satellite geometry,
    user lat/lon, slant range, free-space phase and Gaussian beam pattern.
    """
    users=_region_user_grid(x.geometry_region,x.users,x.geometry_user_radius_km)
    user_ll=np.asarray(users,dtype=float)
    user_xyz=_latlon_to_ecef_np(user_ll[:,0],user_ll[:,1])

    sats,visible_idx,elev_anchor,rng_anchor=_visible_satellites_np(
        x.geometry_region,x.geometry_altitude_km,x.geometry_inclination_deg,
        x.geometry_planes,x.geometry_sats_per_plane,x.geometry_walker_f,
        x.geometry_time_min,x.geometry_min_elevation_deg
    )
    if len(visible_idx)==0:
        return {
            "H":np.zeros((len(users),max(1,x.beams)),dtype=complex),
            "users":users,"satellite_indices":[],"user_elevation_deg":[-90.0]*len(users),
            "user_range_km":[None]*len(users),"user_visible":[False]*len(users),
            "beam_centers":users[:max(1,min(x.beams,len(users)))],
            "visible":False
        }

    selected=visible_idx[np.argsort(elev_anchor[visible_idx])[::-1][:max(1,min(int(x.geometry_satellite_count),len(visible_idx)))]]
    # Current payload applies one common precoder; use the highest-elevation serving satellite.
    sat=sats[selected[0]]

    elev,ranges=_user_elevation_deg_np(sat,user_xyz)

    # Per-user visibility mask: a user below the configured minimum elevation cannot
    # actually see the serving satellite, even when the region anchor point can.
    user_visible=elev>=float(x.geometry_min_elevation_deg)

    # Beam centers follow highest-traffic users later; initial deterministic centers uniformly sample users.
    b=max(1,min(int(x.beams),len(users)))
    center_indices=np.linspace(0,len(users)-1,b,dtype=int)
    centers=user_xyz[center_indices]

    # off-axis matrix users x beams
    H=np.zeros((len(users),b),dtype=complex)
    lam=C_LIGHT/(x.frequency_ghz*1e9)
    gr=db_to_lin(x.geometry_terminal_gain_dbi)
    fixed_loss=db_to_lin(x.geometry_atmospheric_loss_db)
    for j in range(b):
        center=np.broadcast_to(centers[j],user_xyz.shape)
        satv=np.broadcast_to(sat,user_xyz.shape)
        theta=_offaxis_angle_deg(satv,user_xyz,center)
        gt=_gaussian_beam_gain_linear(theta,x.antenna_gain_tx_dbi,x.geometry_beam_hpbw_deg)
        fs_amp=(lam/(4*pi*np.maximum(ranges*1000,1.0)))
        phase=np.exp(-1j*2*pi*(ranges*1000)/lam)
        H[:,j]=np.sqrt(gt*gr/fixed_loss)*fs_amp*phase

    # A non-visible user must not receive any channel energy derived from a
    # satellite it cannot actually see, regardless of the off-axis beam math above.
    H[~user_visible,:]=0.0

    return {
        "H":H,"users":users,"satellite_indices":[int(v) for v in selected],
        "user_elevation_deg":elev.tolist(),"user_range_km":ranges.tolist(),
        "user_visible":user_visible.tolist(),
        "beam_center_indices":center_indices.tolist(),
        "beam_centers":[users[i] for i in center_indices],
        "visible":True
    }

def _precoder_np(H, method="RZF", lam=0.1):
    H=np.asarray(H,dtype=complex)
    if H.size==0:
        return np.zeros((0,0),dtype=complex)
    if method.upper()=="MRT":
        W=H.conj().T
    else:
        G=H@H.conj().T
        reg=(max(1e-9,lam) if method.upper()=="RZF" else 1e-9)
        W=H.conj().T@np.linalg.pinv(G+reg*np.eye(G.shape[0]))
    norms=np.linalg.norm(W,axis=0)
    W=W/np.maximum(norms,1e-15)[None,:]
    return W

def _sinr_np(H,W,total_tx_power_w,noise_dbm,stream_weights=None):
    H=np.asarray(H,dtype=complex); W=np.asarray(W,dtype=complex)
    if H.size==0 or W.size==0:
        return []
    users=H.shape[0]
    streams=W.shape[1]
    if stream_weights is None:
        weights=np.ones(streams)/max(1,streams)
    else:
        weights=np.asarray(stream_weights,dtype=float)
        weights=weights/np.maximum(weights.sum(),1e-18)
    pstreams=max(1e-9,total_tx_power_w)*weights
    HW=H@W
    noise=10**((noise_dbm-30)/10)
    rows=[]
    for i in range(min(users,streams)):
        sig=pstreams[i]*abs(HW[i,i])**2
        interf=sum(pstreams[j]*abs(HW[i,j])**2 for j in range(streams) if j!=i)
        sinr=sig/max(noise+interf,1e-30)
        rows.append({"user":i+1,"signal_w":float(sig),"interference_w":float(interf),"sinr_db":float(10*np.log10(max(sinr,1e-30)))})
    return rows

def _sampled_hpa_metrics_np(order, samples, papr_db, obo_db, p, guard_fraction):
    n_target=max(512,min(16384,int(samples)))
    nfft=256
    oversample=4
    guard=max(0.0,min(0.9,guard_fraction))
    occupied=max(4,min(nfft-4,int(round(nfft*(1.0-guard)))))
    occupied-=occupied%2
    symbol_len=nfft*oversample
    nsym=max(1,int(math.ceil(n_target/symbol_len)))
    m=int(round(math.sqrt(max(4,order))))
    if m*m!=order:
        m=4; order=16
    levels=np.arange(-(m-1),m,2,dtype=float)
    norm=math.sqrt((2/3)*(order-1))

    blocks=[]
    for s in range(nsym):
        X=np.zeros(nfft*oversample,dtype=complex)
        half=occupied//2
        bins=np.concatenate([np.arange(nfft*oversample-half,nfft*oversample),np.arange(1,half+1)])
        rng=np.random.default_rng(12345+s)
        I=rng.choice(levels,size=len(bins))
        Q=rng.choice(levels,size=len(bins))
        X[bins]=(I+1j*Q)/norm
        blocks.append(np.fft.ifft(X)*math.sqrt(len(X)))
    xin=np.concatenate(blocks)[:n_target]
    xin=xin/math.sqrt(max(np.mean(np.abs(xin)**2),1e-30))
    xin=xin*10**(-max(0.0,obo_db)/20)

    actual_papr=10*math.log10(max(np.max(np.abs(xin)**2)/max(np.mean(np.abs(xin)**2),1e-30),1e-30))
    cap=math.sqrt(np.mean(np.abs(xin)**2)*10**(max(.5,papr_db)/10))
    mag=np.abs(xin)
    xin=np.where(mag>cap,xin/np.maximum(mag,1e-30)*cap,xin)

    a=np.abs(xin)
    pp=max(.5,p)
    ao=a/np.power(1+np.power(a,2*pp),1/(2*pp))
    y=np.where(a>0,xin/np.maximum(a,1e-30)*ao,0j)

    den=np.vdot(xin,xin).real
    g=np.vdot(xin,y)/max(den,1e-30)
    err=y-g*xin
    evm=100*math.sqrt(np.vdot(err,err).real/max(np.vdot(g*xin,g*xin).real,1e-30))

    N=1
    while N < len(y):
        N*=2
    P=np.abs(np.fft.fftshift(np.fft.fft(y,n=N)))**2
    c=N//2
    main_half=max(2,int(N*(occupied/(nfft*oversample))/2))
    main=P[c-main_half:c+main_half].sum()
    upper=P[c+main_half:c+3*main_half].sum()
    lower=P[c-3*main_half:c-main_half].sum()
    adjacent=max((upper+lower)/2,1e-30)
    aclr=10*math.log10(max(main,1e-30)/adjacent)

    clipped_papr=10*math.log10(max(np.max(np.abs(xin)**2)/max(np.mean(np.abs(xin)**2),1e-30),1e-30))
    return {"evm_pct":evm,"aclr_proxy_db":aclr,"gain_mag":abs(g),
            "actual_papr_db":actual_papr,"clipped_papr_db":clipped_papr}


def _schedule_throughput_physical(H, schedule, beam_assignment, traffic, bandwidth_mhz,
                                   total_tx_power_w, noise_dbm, method="RZF", lam=0.1,
                                   coding_gap_db=2.0):
    H=np.asarray(H,dtype=complex)
    if H.size==0 or not schedule:
        return {"aggregate_gbps":0.0,"user_mbps":[],"slot_mbps":[],"slot_mean_sinr_db":[]}
    users,beams=H.shape
    user_acc=np.zeros(users,dtype=float)
    slot_rates=[]
    slot_sinr=[]
    gap=db_to_lin(coding_gap_db)
    traffic=np.asarray(traffic,dtype=float)
    traffic=traffic/np.maximum(traffic.sum(),1e-30)

    for row in schedule:
        active=np.where(np.asarray(row)>0)[0]
        if len(active)==0:
            slot_rates.append(0.0); slot_sinr.append(-99.0); continue
        served=np.array([i for i in range(users) if beam_assignment[i] in active],dtype=int)
        if len(served)==0:
            slot_rates.append(0.0); slot_sinr.append(-99.0); continue

        Hs=H[np.ix_(served,active)]
        Ws=_precoder_np(Hs,method,lam)
        weights=traffic[served]
        rows=_sinr_np(Hs,Ws,total_tx_power_w,noise_dbm,weights)
        sinrs=np.array([r["sinr_db"] for r in rows],dtype=float)
        rates=bandwidth_mhz*np.log2(1+np.power(10,sinrs/10)/gap)
        for local_i,u in enumerate(served[:len(rates)]):
            user_acc[u]+=rates[local_i]
        slot_rates.append(float(rates.sum()))
        slot_sinr.append(float(np.mean(sinrs)) if len(sinrs) else -99.0)

    user_avg=user_acc/max(1,len(schedule))
    # A user whose channel row is identically zero (masked out as non-visible, or never
    # scheduled) must show exactly 0 Mbps. The SINR/log2 chain above floors SINR at a
    # small positive epsilon to avoid log(0), which otherwise leaves a non-zero but
    # numerically meaningless residual (~1e-30) instead of a true zero.
    no_channel=np.all(np.abs(H)**2==0,axis=1)
    user_avg=np.where(no_channel,0.0,user_avg)
    return {"aggregate_gbps":float(user_avg.sum()/1000),"user_mbps":user_avg.tolist(),
            "slot_mbps":slot_rates,"slot_mean_sinr_db":slot_sinr}


def _complex_channel_matrix(beams, users, coupling_db):
    """
    Deterministic synthetic channel matrix for architecture studies.
    Diagonal/nearest-beam gains dominate; off-diagonal coupling is controlled in dB.
    """
    import cmath
    b=max(1,beams); u=max(1,users)
    c=10**(coupling_db/20.0)
    H=[]
    for i in range(u):
        row=[]
        home=i % b
        for j in range(b):
            d=min((j-home)%b,(home-j)%b)
            mag=1.0 if j==home else c/(1+d)
            phase=2*pi*((i+1)*(j+2)%17)/17.0
            row.append(mag*complex(math.cos(phase),math.sin(phase)))
        H.append(row)
    return H

def _mat_h_hermitian(H):
    if not H:return []
    rows=len(H); cols=len(H[0])
    out=[[0j for _ in range(rows)] for _ in range(cols)]
    for i in range(rows):
        for j in range(cols):
            out[j][i]=H[i][j].conjugate()
    return out

def _matmul(A,B):
    if not A or not B:return []
    m=len(A); n=len(B); k=len(B[0])
    out=[[0j for _ in range(k)] for _ in range(m)]
    for i in range(m):
        for p in range(n):
            ap=A[i][p]
            for j in range(k):
                out[i][j]+=ap*B[p][j]
    return out

def _invert_matrix(A):
    n=len(A)
    M=[list(row)+[1+0j if i==j else 0j for j in range(n)] for i,row in enumerate(A)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda r:abs(M[r][col]))
        if abs(M[pivot][col])<1e-12:
            M[pivot][col]+=1e-9
        M[col],M[pivot]=M[pivot],M[col]
        pv=M[col][col]
        M[col]=[v/pv for v in M[col]]
        for r in range(n):
            if r==col: continue
            f=M[r][col]
            if abs(f)>0:
                M[r]=[M[r][c]-f*M[col][c] for c in range(2*n)]
    return [row[n:] for row in M]

def _precoder(H, method="RZF", lam=0.1):
    """
    H: users x beams. Returns W: beams x users.
    """
    HH=_mat_h_hermitian(H)
    if method.upper()=="MRT":
        W=HH
    else:
        G=_matmul(H,HH)  # users x users
        if method.upper()=="RZF":
            for i in range(len(G)): G[i][i]+=lam
        else: # ZF
            for i in range(len(G)): G[i][i]+=1e-6
        Ginv=_invert_matrix(G)
        W=_matmul(HH,Ginv)
    # column normalization
    if W:
        cols=len(W[0])
        for j in range(cols):
            norm=math.sqrt(sum(abs(W[i][j])**2 for i in range(len(W))))
            if norm>0:
                for i in range(len(W)): W[i][j]/=norm
    return W

def _sinr_from_precoder(H,W,desired_dbm,noise_dbm):
    users=len(H)
    if users==0:return []
    HW=_matmul(H,W) # users x users
    p0=10**((desired_dbm-30)/10)
    noise=10**((noise_dbm-30)/10)
    out=[]
    for i in range(users):
        sig=p0*abs(HW[i][i])**2
        interf=sum(p0*abs(HW[i][j])**2 for j in range(users) if j!=i)
        sinr=sig/max(noise+interf,1e-18)
        out.append({
            "user":i+1,
            "signal_w":sig,
            "interference_w":interf,
            "sinr_db":10*log10(max(sinr,1e-18))
        })
    return out

def _traffic_vector(users, pattern, hotspot):
    users=max(1,users)
    if pattern=="Uniform":
        v=[1.0]*users
    elif pattern=="Edge-heavy":
        v=[1.0+0.8*abs((i-(users-1)/2)/max(1,(users-1)/2)) for i in range(users)]
    else: # Hotspot
        center=(users-1)/2
        sigma=max(1.0,users/6)
        v=[1.0+(hotspot-1.0)*math.exp(-0.5*((i-center)/sigma)**2) for i in range(users)]
    s=sum(v)
    return [x/s for x in v]

def _beam_hopping_schedule(traffic, beams, timeslots, scheduler, duty):
    """
    Deterministic scheduler abstraction. Produces slot x beam activation map.
    """
    beams=max(1,beams); timeslots=max(1,timeslots)
    beam_load=[0.0]*beams
    for i,t in enumerate(traffic):
        beam_load[i%beams]+=t
    active_per_slot=max(1,int(round(beams*max(0.05,min(1.0,duty)))))
    sched=[]
    debt=[0.0]*beams
    served=[0.0]*beams
    for s in range(timeslots):
        score=[]
        for b in range(beams):
            if scheduler=="Round Robin":
                sc=1.0 if b%beams==(s+b)%beams else 0.5
            elif scheduler=="Max C/I":
                sc=beam_load[b]
            else: # proportional fair proxy
                sc=beam_load[b]/max(1e-6,served[b]+0.05)
            sc+=debt[b]
            score.append((sc,b))
        chosen=[b for _,b in sorted(score,reverse=True)[:active_per_slot]]
        row=[1 if b in chosen else 0 for b in range(beams)]
        sched.append(row)
        for b in range(beams):
            debt[b]+=beam_load[b]
            if b in chosen:
                served[b]+=beam_load[b]
                debt[b]=max(0.0,debt[b]-1.0/timeslots)
    return sched,beam_load

def _qam_symbols(order, n):
    m=int(math.sqrt(max(4,order)))
    if m*m!=order:m=4
    levels=[2*i-(m-1) for i in range(m)]
    norm=math.sqrt((2/3)*(order-1)) if order>1 else 1
    syms=[]
    for k in range(n):
        i=(7*k+3)%m
        q=(11*k+1)%m
        syms.append(complex(levels[i]/norm,levels[q]/norm))
    return syms

def _sampled_hpa_metrics(order, samples, papr_db, obo_db, p, guard_fraction):
    """
    Complex-baseband memoryless Rapp simulation.
    EVM is computed against best-fit complex gain.
    ACLR proxy is obtained from oversampled DFT bin energy outside the nominal occupied band.
    """
    import cmath
    n=max(256,min(4096,samples))
    base=_qam_symbols(order,n)
    peak_scale=10**((papr_db-obo_db)/20)
    xin=[z*peak_scale for z in base]
    y=[]
    for z in xin:
        a=abs(z)
        if a==0:y.append(0j);continue
        ao=hpa_rapp_amplitude(a,1.0,p)
        y.append(z/a*ao)
    # best-fit complex gain
    den=sum(abs(z)**2 for z in xin)
    g=sum(y[i]*xin[i].conjugate() for i in range(n))/max(den,1e-18)
    err=[y[i]-g*xin[i] for i in range(n)]
    evm=100*math.sqrt(sum(abs(e)**2 for e in err)/max(sum(abs(g*z)**2 for z in xin),1e-18))

    # lightweight DFT ACLR proxy using capped bins for runtime
    N=min(512,n)
    sig=y[:N]
    spec=[]
    for k in range(N):
        s=0j
        for t,z in enumerate(sig):
            ang=-2*pi*k*t/N
            s+=z*complex(math.cos(ang),math.sin(ang))
        spec.append(abs(s)**2)
    half=int(N*(1-max(0.05,min(.45,guard_fraction)))/2)
    center=N//2
    # shift zero frequency to center
    spec_shift=spec[N//2:]+spec[:N//2]
    main=sum(spec_shift[max(0,center-half):min(N,center+half)])
    adj=sum(spec_shift[:max(0,center-half)])+sum(spec_shift[min(N,center+half):])
    aclr=10*log10(max(main,1e-18)/max(adj,1e-18))
    return {"evm_pct":evm,"aclr_proxy_db":aclr,"gain_mag":abs(g)}

def hpa_rapp_amplitude(a_in,a_sat=1.0,p=3.0):
    p=max(.5,p)
    return a_in/((1+(a_in/max(a_sat,1e-9))**(2*p))**(1/(2*p)))

def hpa_rapp_metrics(papr_db,obo_db,p=3.0,dpd_enabled=True,dpd_gain_db=2.0):
    peak_amp=math.sqrt(10**((max(0.0,papr_db)-max(0.0,obo_db))/10))
    y=hpa_rapp_amplitude(peak_amp,1.0,p)
    compression_db=20*log10(max(y,1e-12)/max(peak_amp,1e-12))
    recovery=min(abs(compression_db),max(0.0,dpd_gain_db)) if dpd_enabled else 0.0
    eff_comp=compression_db+recovery
    return {
        "compression_db":compression_db,"effective_compression_db":eff_comp,
        "linearity_score":max(0.0,min(100.0,100+12*eff_comp)),
        "operating_margin_db":obo_db-papr_db
    }

def beam_hopping_resource_model(beams,duty,hotspot,reuse,precoding,precoding_eff):
    beams=max(1,beams); duty=max(.01,min(1.0,duty)); reuse=max(1,reuse); hotspot=max(1.0,hotspot)
    demand_match=min(1.35,1+.18*(hotspot-1))
    reuse_gain=min(beams,float(reuse))
    interference_eff=.72 if reuse>1 else .95
    if precoding: interference_eff=min(1.0,interference_eff+.25*max(0.0,min(1.0,precoding_eff)))
    return {
        "demand_match_gain":demand_match,"reuse_gain":reuse_gain,
        "interference_efficiency":interference_eff,
        "normalized_resource_gain":duty*demand_match*reuse_gain*interference_eff,
        "coverage_duty_pct":100*duty
    }

def solve_poisson_1d(x):
    # Depletion-approximation electrostatics:
    # d²phi/dx² = -rho/eps, rho=q*Nnet. Uniform space charge.
    q=1.602176634e-19
    eps0=8.8541878128e-12
    eps=eps0*max(1e-6,x.relative_permittivity)
    L=max(1e-9,x.thickness_um*1e-6)
    n=max(11,min(501,x.grid_points))
    dx=L/(n-1)
    N=x.net_doping_cm3*1e6  # cm^-3 -> m^-3
    rho=q*N

    # Thomas solve for interior nodes with Dirichlet boundaries.
    m=n-2
    a=[1.0]*(m-1)
    b=[-2.0]*m
    c=[1.0]*(m-1)
    rhs=[-rho/eps*dx*dx]*m
    rhs[0]-=x.left_potential_v
    rhs[-1]-=x.right_potential_v

    cp=[0.0]*max(0,m-1)
    dp=[0.0]*m
    if m:
        if m>1: cp[0]=c[0]/b[0]
        dp[0]=rhs[0]/b[0]
        for i in range(1,m):
            den=b[i]-a[i-1]*(cp[i-1] if i-1<len(cp) else 0.0)
            if i<m-1: cp[i]=c[i]/den
            dp[i]=(rhs[i]-a[i-1]*dp[i-1])/den
        vint=[0.0]*m
        vint[-1]=dp[-1]
        for i in range(m-2,-1,-1):
            vint[i]=dp[i]-cp[i]*vint[i+1]
    else:
        vint=[]

    phi=[x.left_potential_v]+vint+[x.right_potential_v]
    xpos=[i*dx for i in range(n)]
    efield=[]
    for i in range(n):
        if i==0: d=(phi[1]-phi[0])/dx
        elif i==n-1: d=(phi[-1]-phi[-2])/dx
        else: d=(phi[i+1]-phi[i-1])/(2*dx)
        efield.append(-d)

    # Analytic constant-charge solution for numerical validation.
    c1=(x.right_potential_v-x.left_potential_v + rho*L*L/(2*eps))/L
    analytic=[-rho*xx*xx/(2*eps)+c1*xx+x.left_potential_v for xx in xpos]
    max_err=max(abs(p-a0) for p,a0 in zip(phi,analytic))

    return {
        "x_um":[round(xx*1e6,6) for xx in xpos],
        "potential_v":[round(v,9) for v in phi],
        "electric_field_v_m":[round(v,3) for v in efield],
        "rho_c_m3":rho,
        "epsilon_f_m":eps,
        "max_field_v_m":max(abs(v) for v in efield),
        "max_numeric_error_v":max_err,
        "physics":"d²φ/dx² = -ρ/ε with uniform depletion charge and Dirichlet boundary potentials",
        "assumption":"1D uniform net ionized dopant charge; mobile-carrier Poisson-Boltzmann coupling is not included."
    }

class ValidatedModel(BaseModel):
    """
    Base for every API input model.

    - Rejects non-finite floats (NaN / Infinity) on any field.
    - Re-validates on model_copy(update=...): pydantic's model_copy intentionally
      skips validation even when validate_assignment=True (it does not go through
      __setattr__ or the constructor), so a value pushed through model_copy could
      otherwise silently bypass every constraint/enum/cross-field check below. The
      codebase updates these models almost exclusively via model_copy(update=...)
      (propagating shared mission parameters between satcom/beam/payload/radiation),
      so without this override those checks would only ever fire once, at the very
      first construction of a default-valued model.
    - validate_assignment=True additionally re-validates plain `model.field = value`
      assignment, for any code path that mutates a model in place.
    """
    # validate_default=True: field defaults given as plain string literals (e.g.
    # architecture:PayloadArchitecture="Regenerative") are otherwise stored as raw
    # strings rather than being coerced into their Enum type until something else
    # touches the field, which shows up as serializer warnings and would let a
    # default silently skip a field_validator/model_validator.
    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    @field_validator("*", mode="after")
    @classmethod
    def _reject_non_finite(cls, v):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("must be a finite number; NaN and Infinity are not allowed")
        return v

    def model_copy(self, *, update=None, deep=False):
        copied = super().model_copy(update=update, deep=deep)
        # Re-validate from the raw field values (copied.__dict__), not
        # copied.model_dump(): model_dump() runs pydantic's serializer over the
        # not-yet-(re)validated copy, which emits spurious
        # "Expected `enum` ... input_type=str" warnings whenever `update` supplied
        # a plain string for an Enum field (which is otherwise perfectly valid
        # input). Going through model_validate() on the raw values still runs
        # every field/model validator exactly the same.
        return type(self).model_validate(dict(copied.__dict__))


class Material(str, Enum):
    SI = "Si"
    SIGE = "SiGe"
    GAAS = "GaAs"
    GAN = "GaN"
    SIC = "SiC"

class ProcessorType(str, Enum):
    FPGA = "FPGA"
    ASIC = "ASIC"

class BeamArchitecture(str, Enum):
    ANALOG = "Analog"
    HYBRID = "Hybrid"
    FULLY_DIGITAL = "Fully Digital"

class PayloadArchitecture(str, Enum):
    BENT_PIPE = "Bent-Pipe"
    REGENERATIVE = "Regenerative"
    FLEXIBLE_DIGITAL = "Flexible Digital"

class Mitigation(str, Enum):
    NONE = "None"
    ECC = "ECC"
    TMR = "TMR"
    TMR_SCRUB = "TMR+Scrub"

class HpaModel(str, Enum):
    RAPP = "Rapp"

class PrecodingMethod(str, Enum):
    RZF = "RZF"
    MRT = "MRT"
    ZF = "ZF"

class TrafficPattern(str, Enum):
    UNIFORM = "Uniform"
    EDGE_HEAVY = "Edge-heavy"
    HOTSPOT = "Hotspot"

class SchedulerType(str, Enum):
    ROUND_ROBIN = "Round Robin"
    MAX_CI = "Max C/I"
    PROPORTIONAL_FAIR = "Proportional Fair"

class RegenerativeStack(str, Enum):
    PHY = "PHY"
    PHY_MAC = "PHY+MAC"
    GNB_DU = "gNB-DU"
    GNB_FULL = "gNB Full"

class Polarization(str, Enum):
    CIRCULAR = "Circular"
    VERTICAL = "Vertical"
    HORIZONTAL = "Horizontal"
    LINEAR = "Linear"

class PoissonModelType(str, Enum):
    DEPLETION = "Depletion"
    POISSON_BOLTZMANN = "Poisson-Boltzmann"
    NONLINEAR = "Nonlinear"

class OptimizeObjective(str, Enum):
    BALANCED = "Balanced"
    LOWEST_COST = "Lowest Cost"
    HIGHEST_CAPACITY = "Highest Capacity"
    LOWEST_MASS = "Lowest Mass"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SensitivityParameter(str, Enum):
    RF_OUTPUT_W = "rf_output_w"
    BANDWIDTH_MHZ = "bandwidth_mhz"
    BEAMS = "beams"
    ELEMENTS = "elements"
    ALTITUDE_KM = "altitude_km"
    SHIELDING_MM_AL = "shielding_mm_al"

class RegionName(str, Enum):
    KOREA = "Korea"
    UAE = "UAE"
    SOUTHEAST_ASIA = "Southeast Asia"

class AnalysisMode(str, Enum):
    FULL = "Full"
    FAST = "Fast"

# Plausible RF band bounds and valid orbital altitude range shared by every model
# that carries a frequency or altitude field. These are deliberately generous
# (they must not reject any legitimate satcom/deep-tech scenario) while still
# catching physically nonsensical input (0 Hz, negative altitude, a "GHz" value
# that is actually in Hz, an altitude below the Karman line or beyond a
# reasonable super-GEO/graveyard orbit).
FREQ_GHZ_MIN=0.1
FREQ_GHZ_MAX=300.0
ALTITUDE_KM_MIN=160.0
ALTITUDE_KM_MAX=40000.0

class SatcomInput(ValidatedModel):
    material:Material="GaN"
    part_pa:str="PA-GaN-Ka-20W"
    part_lna:str="LNA-GaAs-Ka"
    altitude_km:float=Field(1280,ge=ALTITUDE_KM_MIN,le=ALTITUDE_KM_MAX)
    min_elevation_deg:float=Field(20,ge=0,le=90)
    frequency_ghz:float=Field(20,gt=0,ge=FREQ_GHZ_MIN,le=FREQ_GHZ_MAX)
    bandwidth_mhz:float=Field(100,gt=0)
    rf_output_w:float=20
    tx_gain_dbi:float=34
    rx_gain_dbi:float=42
    losses_db:float=3
    antenna_temp_k:float=290
    bus_power_w:float=1800
    payload_share:float=.5
    antenna_diameter_m:float=.45
    antenna_efficiency:float=.62
    structure_mass_kg:float=180
    base_payload_mass_kg:float=75
    base_cost_musd:float=12
    radiator_w_m2:float=350
    mission_years:float=5
    array_elements:int=256
    beams:int=8
    processor:ProcessorType="FPGA"
    processor_tops:float=1.5
    coding_gap_db:float=2.0
    max_spectral_eff:float=6.0
    atmospheric_loss_db:float=0.0
    radiator_temp_k:float=323.15
    radiator_emissivity:float=0.85
    radiator_view_factor:float=0.80
    # Multiplicative perturbation applied on top of the material/part-derived PA
    # efficiency (see satcom()). Defaults to 1.0 (no perturbation) so every
    # existing caller is unaffected; Monte Carlo draws this per-run from
    # MonteCarloInput.pa_eff_sigma_pct.
    pa_eff_perturbation_mult:float=Field(1.0,gt=0)

class BeamInput(ValidatedModel):
    elements:int=256
    beams:int=8
    bandwidth_mhz:float=Field(100,gt=0)
    sample_gsps:float=1.0
    bits:int=12
    architecture:BeamArchitecture="Fully Digital"
    processor:ProcessorType="FPGA"
    available_tops:float=2.0
    available_power_w:float=180
    phase_bits:int=6
    amplitude_bits:int=6
    calibration_error_deg:float=2.0
    element_spacing_lambda:float=.5
    max_scan_deg:float=60.0

class RadInput(ValidatedModel):
    mission_years:float=5
    shielding_mm_al:float=2
    tid_env_krad_yr:float=2
    tid_tolerance_krad:float=30
    dd_env_arb_yr:float=1
    dd_tolerance_arb:float=10
    seu_rate_device_day:float=.002
    sel_rate_device_day:float=.00002
    sensitive_devices:int=25
    mitigation:Mitigation="TMR+Scrub"
    scrub_interval_min:float=10
    spares:int=1
    reset_recovery_sec:float=5
    service_nodes:int=128

class PayloadInput(ValidatedModel):
    architecture:PayloadArchitecture="Regenerative"
    frequency_ghz:float=Field(20,gt=0,ge=FREQ_GHZ_MIN,le=FREQ_GHZ_MAX)
    bandwidth_mhz:float=500
    input_power_dbw:float=-115
    antenna_gain_rx_dbi:float=35
    antenna_gain_tx_dbi:float=35
    lna_gain_db:float=30
    lna_nf_db:float=1.3
    filter_loss_db:float=1.0
    mixer_loss_db:float=6.0
    channelizer_loss_db:float=1.5
    switch_loss_db:float=1.0
    pa_gain_db:float=28
    pa_output_w:float=20
    pa_efficiency:float=.46
    channels:int=16
    beams:int=8
    processor_power_w:float=120
    converter_power_w:float=55
    other_power_w:float=90
    dry_mass_kg:float=65
    thermal_margin_pct:float=20
    radiator_temp_k:float=323.15
    radiator_emissivity:float=0.85
    radiator_view_factor:float=0.80
    papr_db:float=8.0
    output_backoff_db:float=3.0
    hpa_model:HpaModel="Rapp"
    rapp_p:float=3.0
    dpd_enabled:bool=True
    dpd_gain_db:float=2.0
    frequency_reuse:int=4
    beam_hopping_duty:float=0.50
    traffic_hotspot_factor:float=2.0
    precoding_enabled:bool=False
    precoding_efficiency:float=0.80
    channelizer_granularity_mhz:float=5.0
    routing_matrix_inputs:int=8
    routing_matrix_outputs:int=8
    regenerative_stack:RegenerativeStack="PHY"
    isl_offload_fraction:float=0.0
    # V1.1 interference / traffic / waveform
    users:int=16
    user_noise_dbm:float=-100.0
    desired_signal_dbm:float=-80.0
    cochannel_coupling_db:float=-18.0
    precoding_method:PrecodingMethod="RZF"
    rzf_lambda:float=0.1
    traffic_pattern:TrafficPattern="Hotspot"
    scheduler:SchedulerType="Proportional Fair"
    timeslots:int=16
    hpa_samples:int=2048
    modulation_order:int=16
    aclr_guard_fraction:float=0.15
    # V1.2 geometry-resolved channel
    geometry_channel_enabled:bool=True
    geometry_region:RegionName="Korea"
    geometry_time_min:float=0.0
    geometry_user_radius_km:float=250.0
    geometry_satellite_count:int=1
    geometry_inclination_deg:float=Field(42.0,ge=0,le=180)
    geometry_planes:int=Field(16,ge=1,le=60)
    geometry_sats_per_plane:int=Field(8,ge=1,le=60)
    geometry_walker_f:int=Field(1,ge=0)
    geometry_altitude_km:float=Field(1280.0,ge=ALTITUDE_KM_MIN,le=ALTITUDE_KM_MAX)
    geometry_min_elevation_deg:float=Field(10.0,ge=0,le=90)
    geometry_terminal_gain_dbi:float=32.0
    geometry_beam_hpbw_deg:float=2.5
    geometry_atmospheric_loss_db:float=1.0
    geometry_total_tx_power_w:float=40.0
    analysis_mode:AnalysisMode="Full"

    @model_validator(mode="after")
    def _check_walker_phasing_feasible(self):
        # Walker Delta-pattern phasing convention: F (walker_f) must satisfy
        # 0 <= F < planes, otherwise the constellation phasing is not well-defined
        # for the given plane count. The propagation code used to silently wrap
        # an out-of-range F via `% planes`; that hides a genuinely invalid input
        # (e.g. F equal to or larger than planes) instead of rejecting it.
        if self.geometry_walker_f >= self.geometry_planes:
            raise ValueError(
                f"geometry_walker_f ({self.geometry_walker_f}) must be less than "
                f"geometry_planes ({self.geometry_planes}) for a valid Walker "
                "Delta-pattern phasing (0 <= F < planes)"
            )
        return self


def satcom(x:SatcomInput):
    mat=MATERIALS.get(x.material,MATERIALS["GaN"])
    pa=PARTS.get(x.part_pa,PARTS["PA-GaN-Ka-20W"])
    lna=PARTS.get(x.part_lna,PARTS["LNA-GaAs-Ka"])

    # Semiconductor / PA energy conservation. pa_eff_perturbation_mult defaults to
    # 1.0 (no-op) and is only driven away from 1.0 by Monte Carlo sampling
    # (pa_eff_sigma_pct), so this is a pure pass-through for every other caller.
    eff=max(0.01,min(0.95,pa.get("eff",mat["pa_eff"])*x.pa_eff_perturbation_mult))
    pa_dc=x.rf_output_w/eff
    pa_heat=max(0.0,pa_dc-x.rf_output_w)

    # Circular-orbit geometry
    dist=_cached_slant_range(round(x.altitude_km,6),round(x.min_elevation_deg,6))
    psi,foot_r,foot_a=_cached_footprint(round(x.altitude_km,6),round(x.min_elevation_deg,6))
    period,speed=_cached_orbit_scalar(round(x.altitude_km,6))
    doppler=max_orbital_doppler_hz(x.frequency_ghz,x.altitude_km)

    # Antenna aperture physics. Tx gain is derived from the physical aperture.
    aperture_gain=_cached_antenna_gain(round(x.antenna_diameter_m,6),round(x.antenna_efficiency,6),round(x.frequency_ghz,6))
    gt=aperture_gain
    gr=x.rx_gain_dbi  # ground-terminal gain remains a direct user input until its aperture is modeled.
    total_losses=x.losses_db+x.atmospheric_loss_db

    # Friis link equation + receiver noise
    f=_cached_fspl(round(x.frequency_ghz,6),round(dist,6))
    nf=lna.get("nf_db",mat["lna_nf"])
    tr=noise_temp_from_nf_db(nf)
    ts=max(1.0,x.antenna_temp_k+tr)
    rx=friis_received_power_dbw(x.rf_output_w,gt,gr,x.frequency_ghz,dist,total_losses)
    n0_dbw_hz=K_DBW+10*log10(ts)
    cn0=rx-n0_dbw_hz
    snr=cn0-10*log10(x.bandwidth_mhz*1e6)

    # Shannon upper bound and implementation-gap achievable-rate model
    snrl=db_to_lin(snr)
    shannon_se=log2(1.0+snrl)
    practical_se=practical_spectral_efficiency(snr,x.coding_gap_db,x.max_spectral_eff)
    shannon_mbps=x.bandwidth_mhz*shannon_se
    mbps=x.bandwidth_mhz*practical_se

    # Engineering mass/compute models (explicitly not fundamental physics)
    antenna_mass=9.5*x.antenna_diameter_m**2
    array_mass=.018*x.array_elements
    digital_power=(38 if x.processor=="FPGA" else 18)+x.processor_tops*(12 if x.processor=="FPGA" else 4.0)+.035*x.array_elements*sqrt(max(x.beams,1))
    modeled_payload_power=pa_dc+digital_power+lna.get("power_w",2)+55
    payload_budget=x.bus_power_w*x.payload_share
    spare=payload_budget-modeled_payload_power

    # Stefan-Boltzmann radiator sizing
    total_heat=pa_heat+digital_power*.78+40
    radiator_area=thermal_radiator_area(
        total_heat,x.radiator_temp_k,x.radiator_emissivity,x.radiator_view_factor,0.0
    )
    radiator_mass=6.5*radiator_area

    payload_mass=x.base_payload_mass_kg+antenna_mass+array_mass+radiator_mass+(pa.get("mass_g",0)+lna.get("mass_g",0))/1000
    total_mass=x.structure_mass_kg+payload_mass

    # Programmatic / economic proxies are intentionally separated from physics.
    bom_cost=(pa.get("cost_kusd",0)+lna.get("cost_kusd",0))/1000
    digital_cost=.35 if x.processor=="FPGA" else .65
    payload_cost=x.base_cost_musd+bom_cost+digital_cost+.004*x.array_elements
    launch_cost_proxy=total_mass*.018
    total_cost=payload_cost+launch_cost_proxy

    global_floor=4*pi*R_EARTH**2/max(foot_a,1)
    service_floor=global_floor*1.35
    compute_beams=min(x.beams,max(1,x.processor_tops/(.012*x.beams*(x.array_elements/256)*max(.5,x.bandwidth_mhz/100))))
    agg=mbps*compute_beams/1000

    return {
      "device":{"pa_eff_pct":round(eff*100,1),"pa_dc_w":round(pa_dc,1),"heat_w":round(pa_heat,1),"lna_nf_db":nf},
      "antenna":{"physical_gain_dbi":round(aperture_gain,2),"used_tx_gain_dbi":round(gt,2),"ground_rx_gain_dbi":round(gr,2),"diameter_m":x.antenna_diameter_m,"mass_kg":round(antenna_mass,2)},
      "payload":{"power_w":round(modeled_payload_power,1),"budget_w":round(payload_budget,1),"spare_w":round(spare,1),"mass_kg":round(payload_mass,1),"radiator_m2":round(radiator_area,3),"radiator_mass_kg":round(radiator_mass,1),"heat_w":round(total_heat,1)},
      "link":{"slant_km":round(dist,1),"fspl_db":round(f,2),"total_losses_db":round(total_losses,2),"rx_dbw":round(rx,2),"noise_temp_k":round(ts,1),"n0_dbw_hz":round(n0_dbw_hz,2),"cn0_dbhz":round(cn0,2),"snr_db":round(snr,2),"shannon_se":round(shannon_se,3),"practical_se":round(practical_se,3),"shannon_mbps":round(shannon_mbps,1),"mbps_beam":round(mbps,1),"aggregate_gbps":round(agg,2),"max_doppler_khz":round(doppler/1e3,1)},
      "orbit":{"period_min":round(period/60,2),"speed_km_s":round(speed,3),"footprint_radius_km":round(foot_r,1),"footprint_area_km2":round(foot_a,0),"global_floor":round(global_floor,1),"service_floor_proxy":round(service_floor,1)},
      "program":{"total_mass_kg":round(total_mass,1),"payload_cost_musd":round(payload_cost,2),"launch_cost_proxy_musd":round(launch_cost_proxy,2),"total_cost_proxy_musd":round(total_cost,2)},
      "physics":{
        "link":"Friis transmission + kTB noise + Shannon capacity with implementation gap",
        "antenna":"G = η(πD/λ)^2",
        "orbit":"circular two-body Kepler geometry",
        "thermal":"Q = εσAF(T^4 - Tspace^4)",
      },
      "parts":{"pa":pa,"lna":lna},
      "warnings":[w for w in [
        "탑재체 전력예산 초과" if spare<0 else "",
        "Tx gain은 V0.8부터 입력값이 아니라 안테나 직경·효율·주파수에서 계산됩니다.",
        "대기/강우 손실은 atmospheric_loss_db 입력으로 분리되어 있으며 현재 자동 기상모델은 사용하지 않습니다.",
        "질량·비용·디지털 전력은 engineering model이며 물리 법칙 자체가 아닙니다."
      ] if w]
    }

def beamforming(x:BeamInput):
    # Computational load model: complex MAC operations scale with N_elements × N_beams × bandwidth.
    arch_factor={"Analog":0.18,"Hybrid":0.48,"Fully Digital":1.0}.get(x.architecture,1.0)
    complex_ops=x.elements*x.beams*x.bandwidth_mhz*1e6*8*arch_factor
    req_tops=complex_ops/1e12

    converter_paths=x.elements if x.architecture=="Fully Digital" else max(x.beams,int(sqrt(x.elements)))
    conv_power=converter_paths*x.sample_gsps*(0.22+0.045*max(0,x.bits-8))
    proc_eff=0.07 if x.processor=="FPGA" else 0.28
    proc_power=18+x.available_tops/max(proc_eff,1e-6)
    phase_power=x.elements*(.045 if x.architecture!="Fully Digital" else .012)
    total=conv_power+proc_power+phase_power

    compute_margin=x.available_tops/max(req_tops,1e-12)
    power_margin=x.available_power_w-total
    max_beams_compute=max(0,int(x.beams*min(1,compute_margin)))
    max_beams_power=max(0,int(x.beams*min(1,x.available_power_w/max(total,1e-9))))
    eff_beams=max(0,min(x.beams,max_beams_compute,max_beams_power))

    # Phase-quantization physics: uniform quantization error RMS = Δ/sqrt(12).
    phase_step=2*pi/(2**max(1,x.phase_bits))
    sigma_quant=phase_step/sqrt(12)
    sigma_cal=radians(max(0,x.calibration_error_deg))
    sigma_total=sqrt(sigma_quant**2+sigma_cal**2)
    coherent_eff=math.exp(-(sigma_total**2))
    phase_loss_db=-10*log10(max(coherent_eff,1e-12))

    # Ideal coherent array gain relative to one element.
    ideal_array_gain_db=10*log10(max(1,x.elements))
    scan_rad=radians(max(0,min(89.0,x.max_scan_deg)))
    scan_projection=max(0.05,cos(scan_rad))
    scan_loss_db=-10*log10(scan_projection)

    # Grating-lobe-free spacing for scan to theta_max: d/λ <= 1/(1+sin(theta_max)).
    safe_spacing=1/(1+sin(scan_rad))
    grating_risk="LOW" if x.element_spacing_lambda<=safe_spacing else ("MEDIUM" if x.element_spacing_lambda<=0.7 else "HIGH")

    return {
      "compute":{"required_tops":round(req_tops,3),"available_tops":x.available_tops,"margin_x":round(compute_margin,2),"effective_beams":eff_beams},
      "power":{"converter_w":round(conv_power,1),"processor_w":round(proc_power,1),"phase_control_w":round(phase_power,1),"total_w":round(total,1),"margin_w":round(power_margin,1)},
      "quality":{"phase_quant_rms_deg":round(degrees(sigma_quant),3),"phase_total_rms_deg":round(degrees(sigma_total),3),"coherent_efficiency_pct":round(coherent_eff*100,2),"phase_error_loss_db":round(phase_loss_db,3),"ideal_array_gain_db":round(ideal_array_gain_db,2),"scan_loss_db":round(scan_loss_db,2),"safe_spacing_lambda":round(safe_spacing,3),"grating_lobe_risk":grating_risk},
      "architecture":{"converter_paths":converter_paths,"arch_factor":arch_factor},
      "physics":{"phase_error":"ηcoh ≈ exp(-σφ²)","grating":"d/λ ≤ 1/(1+sin θscan)","array_gain":"Garray ≈ 10log10(N) ideal coherent gain"},
      "warnings":[w for w in [
        "연산량 부족으로 요청 빔 수를 모두 처리하기 어렵습니다." if compute_margin<1 else "",
        "전력예산 부족으로 요청 빔 수를 모두 처리하기 어렵습니다." if power_margin<0 else "",
        f"{x.max_scan_deg:.0f}° scan 기준 무 grating-lobe 간격은 약 {safe_spacing:.3f}λ 이하입니다." if x.element_spacing_lambda>safe_spacing else "",
        "ADC/processor 전력은 데이터시트 기반 물리모델이 아니라 engineering scaling model입니다."
      ] if w]
    }

def radiation(x:RadInput):
    shield=1/(1+.22*x.shielding_mm_al)
    tid=x.tid_env_krad_yr*x.mission_years*shield
    dd=x.dd_env_arb_yr*x.mission_years*shield
    tid_use=tid/x.tid_tolerance_krad
    dd_use=dd/x.dd_tolerance_arb
    mf={"None":1.0,"ECC":.35,"TMR":.18,"TMR+Scrub":.07}.get(x.mitigation,.07)
    scrub_gain=min(1,max(.03,x.scrub_interval_min/60))
    seu_day=x.seu_rate_device_day*x.sensitive_devices*mf*scrub_gain
    sel_day=x.sel_rate_device_day*x.sensitive_devices
    mission_seu=seu_day*365.25*x.mission_years
    mission_sel=sel_day*365.25*x.mission_years
    downtime_hr=(mission_seu*x.reset_recovery_sec+mission_sel*180)/3600
    availability=max(0,100*(1-downtime_hr/(x.mission_years*365.25*24)))
    node_loss_prob=min(.999,1-pow(2.718281828,-mission_sel/(x.spares+1)))
    fleet_expected=x.service_nodes*node_loss_prob
    risk=max(tid_use,dd_use,min(1,mission_sel/3))
    cls="LOW" if risk<.35 else ("MEDIUM" if risk<.75 else "HIGH")
    return {
      "dose":{"mission_tid_krad":round(tid,2),"tid_usage_pct":round(100*tid_use,1),"dd_usage_pct":round(100*dd_use,1),"shield_factor":round(shield,3)},
      "see":{"seu_day":round(seu_day,5),"mission_seu":round(mission_seu,1),"sel_day":round(sel_day,6),"mission_sel":round(mission_sel,3)},
      "service":{"electronics_availability_pct":round(availability,6),"downtime_hr":round(downtime_hr,3),"node_loss_probability_pct":round(node_loss_prob*100,3),"fleet_expected_nodes_at_risk":round(fleet_expected,2)},
      "risk":{"class":cls,"score_pct":round(min(100,risk*100),1)},
      "warnings":[w for w in [
        "TID 내성 예산의 70%를 초과합니다." if tid_use>.7 else "",
        "SEL 누적 기대값이 높습니다. latch-up 보호 및 전원 차단/복구 설계 검토가 필요합니다." if mission_sel>.5 else "",
        "실제 RHA는 궤도 환경·부품 시험자료·차폐 형상·회로/소프트웨어 완화를 함께 검증해야 합니다."
      ] if w]
    }

def payload(x:PayloadInput):
    stages=[("LNA",x.lna_gain_db),("Filter",-x.filter_loss_db),("Mixer",-x.mixer_loss_db),
            ("Channelizer",-x.channelizer_loss_db),("Switch",-x.switch_loss_db),("PA",x.pa_gain_db)]
    level=x.input_power_dbw; chain=[]
    for name,gain in stages:
        level+=gain
        chain.append({"stage":name,"gain_db":gain,"level_dbw":round(level,2)})
    pa_limit=dbw(x.pa_output_w)
    saturated=level>pa_limit
    output=min(level,pa_limit)

    hpa=hpa_rapp_metrics(x.papr_db,x.output_backoff_db,x.rapp_p,x.dpd_enabled,x.dpd_gain_db)
    average_rf_w=x.pa_output_w/(10**(x.output_backoff_db/10))
    pa_dc=average_rf_w/max(x.pa_efficiency,.01)

    arch_factor={"Bent-Pipe":.65,"Regenerative":1.0,"Flexible Digital":1.12}.get(x.architecture,1.0)
    regen_factor={"PHY":1.0,"PHY+MAC":1.25,"gNB-DU":1.55,"gNB Full":1.9}.get(x.regenerative_stack,1.0)
    matrix_ports=max(1,x.routing_matrix_inputs*x.routing_matrix_outputs)
    routing_power=(.12 if x.architecture!="Bent-Pipe" else .03)*matrix_ports
    bins=max(1,int((x.channels*x.bandwidth_mhz)/max(x.channelizer_granularity_mhz,.1)))
    channelizer_power=.035*bins*arch_factor
    regen_power=x.processor_power_w*regen_factor if x.architecture!="Bent-Pipe" else .25*x.processor_power_w
    converter_power=x.converter_power_w*(1.0 if x.architecture!="Bent-Pipe" else .45)

    bh=beam_hopping_resource_model(x.beams,x.beam_hopping_duty,x.traffic_hotspot_factor,
                                   x.frequency_reuse,x.precoding_enabled,x.precoding_efficiency)

    total_power=pa_dc+regen_power+converter_power+routing_power+channelizer_power+x.other_power_w
    heat=max(0.0,total_power-average_rf_w)
    radiator=thermal_radiator_area(heat,x.radiator_temp_k,x.radiator_emissivity,x.radiator_view_factor,x.thermal_margin_pct)
    processed_bw=x.channels*x.bandwidth_mhz
    service_index=arch_factor*x.beams*x.bandwidth_mhz/100*bh["normalized_resource_gain"]
    flexibility={"Bent-Pipe":35,"Regenerative":78,"Flexible Digital":96}.get(x.architecture,75)
    complexity={"Bent-Pipe":30,"Regenerative":74,"Flexible Digital":91}.get(x.architecture,68)
    mass=x.dry_mass_kg+6.5*radiator+.45*x.channels+.14*x.beams+.015*matrix_ports
    feeder=max(0.0,1-max(0.0,min(1.0,x.isl_offload_fraction)))

    # Co-channel interference and precoding
    geometry=_geometry_channel_matrix(x) if x.geometry_channel_enabled else None
    if x.geometry_channel_enabled:
        # geometry["visible"] False means no satellite is visible anywhere in the
        # region (H is then all-zero, per _geometry_channel_matrix). That must flow
        # through as genuine zero SINR/throughput below -- it must NOT be replaced by
        # the synthetic/idealized architecture-level channel model, which would
        # fabricate a non-zero capacity for a scenario that has no actual link.
        H=np.asarray(geometry["H"],dtype=complex)
        W=_precoder_np(H,x.precoding_method,x.rzf_lambda) if x.precoding_enabled else _precoder_np(H,"MRT",0.0)
        # traffic shares become stream-power weights for physically connected SINR
        traffic=_traffic_vector(x.users,x.traffic_pattern,x.traffic_hotspot_factor)
        stream_weights=traffic[:W.shape[1]]
        sinr_rows=_sinr_np(H,W,x.geometry_total_tx_power_w,x.user_noise_dbm,stream_weights)
    else:
        H=np.asarray(_complex_channel_matrix(x.beams,x.users,x.cochannel_coupling_db),dtype=complex)
        W=_precoder_np(H,x.precoding_method,x.rzf_lambda) if x.precoding_enabled else _precoder_np(H,"MRT",0.0)
        sinr_rows=_sinr_np(H,W,x.geometry_total_tx_power_w,x.user_noise_dbm)
        traffic=_traffic_vector(x.users,x.traffic_pattern,x.traffic_hotspot_factor)
    sinr_vals=[r["sinr_db"] for r in sinr_rows]
    mean_sinr=sum(sinr_vals)/len(sinr_vals) if sinr_vals else -99
    p5_sinr=sorted(sinr_vals)[max(0,int(.05*len(sinr_vals))-1)] if sinr_vals else -99

    # H may carry fewer columns than x.beams when geometry resolves fewer beams than users;
    # the schedule must be built over H's actual beam count so scheduled indices stay in bounds.
    n_beams_actual=H.shape[1] if H.size else x.beams
    schedule,beam_load=_beam_hopping_schedule(traffic,n_beams_actual,x.timeslots,x.scheduler,x.beam_hopping_duty)
    beam_assignment=np.argmax(np.abs(H),axis=1).astype(int) if H.size else np.zeros(len(traffic),dtype=int)
    throughput=_schedule_throughput_physical(H,schedule,beam_assignment,traffic,x.bandwidth_mhz,
        x.geometry_total_tx_power_w,x.user_noise_dbm,x.precoding_method if x.precoding_enabled else "MRT",x.rzf_lambda,2.0)

    if x.analysis_mode.lower()=="fast":
        # Fast screening model for optimizer/Monte Carlo: preserve schema without FFT.
        comp=abs(hpa["effective_compression_db"])
        waveform={
            "evm_pct":max(0.0,4.5*comp),
            "aclr_proxy_db":max(0.0,28.0-5.0*comp),
            "gain_mag":10**(hpa["effective_compression_db"]/20),
            "actual_papr_db":x.papr_db,
            "clipped_papr_db":min(x.papr_db,max(0.5,x.output_backoff_db+4.0))
        }
    else:
        waveform=_sampled_hpa_metrics_np(
            x.modulation_order,x.hpa_samples,x.papr_db,x.output_backoff_db,x.rapp_p,x.aclr_guard_fraction
        )
    return {
      "chain":chain,
      "rf":{"output_dbw":round(output,2),"pa_limit_dbw":round(pa_limit,2),"saturated":saturated,
            "average_rf_w":round(average_rf_w,2),
            "hpa_compression_db":round(hpa["compression_db"],3),
            "hpa_effective_compression_db":round(hpa["effective_compression_db"],3),
            "hpa_linearity_score":round(hpa["linearity_score"],1),
            "operating_margin_db":round(hpa["operating_margin_db"],2)},
      "digital":{"regenerative_stack":x.regenerative_stack,"routing_matrix":f"{x.routing_matrix_inputs}x{x.routing_matrix_outputs}",
                 "channelizer_bins_proxy":bins,"channelizer_power_w":round(channelizer_power,1),
                 "routing_power_w":round(routing_power,1),"regenerative_power_w":round(regen_power,1),
                 "converter_power_w":round(converter_power,1)},
      "resource":{**{k:round(v,3) for k,v in bh.items()},"frequency_reuse":x.frequency_reuse,
                  "precoding_enabled":x.precoding_enabled,"precoding_method":x.precoding_method,
                  "mean_sinr_db":round(mean_sinr,3),"p5_sinr_db":round(p5_sinr,3),
                  "feeder_load_fraction":round(feeder,3)},
      "waveform":{"modulation_order":x.modulation_order,"evm_pct":round(waveform["evm_pct"],3),
                  "aclr_proxy_db":round(waveform["aclr_proxy_db"],3),"best_fit_gain":round(waveform["gain_mag"],4),
                  "actual_papr_db":round(waveform["actual_papr_db"],3),"clipped_papr_db":round(waveform["clipped_papr_db"],3)},
      "interference":{"users":x.users,"sinr":sinr_rows,
                      "channel_power_matrix":np.round(np.abs(H)**2,12).tolist(),
                      "precoder_power_matrix":np.round(np.abs(W)**2,8).tolist()},
      "traffic":{"pattern":x.traffic_pattern,"scheduler":x.scheduler,"user_share":[round(v,5) for v in traffic],
                 "beam_load":[round(v,5) for v in beam_load],"schedule":schedule,
                 "user_throughput_mbps":[round(v,3) for v in throughput["user_mbps"]],
                 "slot_throughput_mbps":[round(v,3) for v in throughput["slot_mbps"]],
                 "slot_mean_sinr_db":[round(v,3) for v in throughput["slot_mean_sinr_db"]],
                 "beam_assignment":[int(v) for v in beam_assignment.tolist()],
                 "aggregate_scheduled_gbps":round(throughput["aggregate_gbps"],3)},
      "geometry":{
          "enabled":x.geometry_channel_enabled,
          "visible":bool(geometry["visible"]) if geometry else False,
          "region":x.geometry_region,
          "time_min":x.geometry_time_min,
          "satellite_indices":geometry["satellite_indices"] if geometry else [],
          "users":[{"lat":round(v[0],5),"lon":round(v[1],5)} for v in (geometry["users"] if geometry else [])],
          "user_elevation_deg":[round(v,3) for v in (geometry["user_elevation_deg"] if geometry else [])],
          "user_range_km":[round(v,3) if v is not None else None for v in (geometry["user_range_km"] if geometry else [])],
          "user_visible":[bool(v) for v in (geometry.get("user_visible",[]) if geometry else [])],
          "beam_centers":[{"lat":round(v[0],5),"lon":round(v[1],5)} for v in (geometry["beam_centers"] if geometry else [])],
          "channel_source":("Walker geometry + range + phase + Gaussian beam pattern" if geometry and geometry["visible"]
                             else "no visible satellite (zero channel; no synthetic substitute)" if x.geometry_channel_enabled
                             else "synthetic architecture-level channel model")
      },
      "power":{"pa_dc_w":round(pa_dc,1),"total_w":round(total_power,1),"heat_w":round(heat,1),"radiator_m2":round(radiator,3)},
      "system":{"mass_kg":round(mass,1),"processed_bw_mhz":round(processed_bw,1),"service_index":round(service_index,2),
                "flexibility_score":flexibility,"complexity_score":complexity},
      "physics":{"thermal":"Stefan-Boltzmann","hpa":"Rapp AM/AM behavioral model",
                 "resource":"Beam hopping / reuse scheduler is engineering; SINR and precoder matrix are signal-domain calculations",
                 "waveform":"Memoryless sampled Rapp baseband simulation; EVM from best-fit gain, ACLR is spectral proxy"},
      "warnings":[w for w in [
        "RF chain requested level exceeds PA saturation limit." if saturated else "",
        "PAPR exceeds output backoff; nonlinear HPA compression is expected." if x.papr_db>x.output_backoff_db else "",
        "Frequency reuse >1 requires explicit co-channel SINR / precoding validation." if x.frequency_reuse>1 else "",
        "Regenerative processing increases onboard compute, software verification and thermal burden." if x.architecture!="Bent-Pipe" else "",
        "Beam-hopping gain is a scheduler abstraction, not a propagation law.",
        "No visible serving satellite at the selected geometry/time; channel is zero and throughput is 0 Mbps for every user (no synthetic fallback)." if x.geometry_channel_enabled and (not geometry or not geometry["visible"]) else "",
        "Sampled HPA EVM/ACLR remains a memoryless baseband approximation; no PA memory effects or spectral-mask certification."
      ] if w]
    }

class PropagationInput(ValidatedModel):
    frequency_ghz: float = Field(20.0,gt=0,ge=FREQ_GHZ_MIN,le=FREQ_GHZ_MAX)
    elevation_deg: float = Field(30.0,ge=0,le=90)
    rain_rate_mm_h: float = Field(25.0,ge=0)
    polarization: Polarization = "Circular"
    polarization_tilt_deg: float = Field(45.0,ge=0,le=180)
    rain_height_km: float = Field(5.0,ge=0)
    station_height_km: float = Field(0.1,ge=0)
    path_reduction_factor: float = Field(1.0,ge=0,le=1)

class PassTimelineInput(ValidatedModel):
    altitude_km: float = Field(1280,ge=ALTITUDE_KM_MIN,le=ALTITUDE_KM_MAX)
    inclination_deg: float = Field(42,ge=0,le=180)
    planes: int = Field(16, ge=1, le=60)
    sats_per_plane: int = Field(8, ge=1, le=60)
    walker_f: int = Field(1,ge=0)
    region: RegionName = "Korea"
    min_elevation_deg: float = Field(20,ge=0,le=90)
    duration_hours: float = Field(6, ge=0.01, le=72)
    time_step_sec: float = Field(60, ge=5, le=3600)

    @model_validator(mode="after")
    def _check_walker_phasing_feasible(self):
        if self.walker_f >= self.planes:
            raise ValueError(
                f"walker_f ({self.walker_f}) must be less than planes ({self.planes}) "
                "for a valid Walker Delta-pattern phasing (0 <= F < planes)"
            )
        return self

class PoissonDeviceInput(ValidatedModel):
    thickness_um: float = Field(1.0,gt=0)
    net_doping_cm3: float = 1e15
    relative_permittivity: float = Field(11.7,gt=0)
    left_potential_v: float = 0.0
    right_potential_v: float = 0.5
    grid_points: int = Field(121,ge=3,le=100000)
    model: PoissonModelType = "Depletion"
    temperature_k: float = Field(300.0,gt=0)
    intrinsic_cm3: float = Field(1.0e10,gt=0)
    carrier_sign: int = Field(1,ge=-1,le=1)
    max_iterations: int = Field(80,ge=1,le=100000)
    tolerance_v: float = Field(1e-7,gt=0)

    @field_validator("carrier_sign")
    @classmethod
    def _carrier_sign_nonzero(cls, v):
        if v == 0:
            raise ValueError("carrier_sign must be -1 or 1 (0 is not a valid carrier sign)")
        return v

def api_satcom(x:SatcomInput): return satcom(x)

def api_beam(x:BeamInput): return beamforming(x)

def api_rad(x:RadInput): return radiation(x)

def api_payload(x:PayloadInput): return payload(x)

def api_parts(): return PARTS

def orbit_sweep(x:SatcomInput):
    out=[]
    for alt in [500,888,1280]:
        r=satcom(x.model_copy(update={"altitude_km":alt}))
        out.append({"altitude_km":alt,"snr_db":r["link"]["snr_db"],"mbps_beam":r["link"]["mbps_beam"],"footprint_radius_km":r["orbit"]["footprint_radius_km"],"service_floor_proxy":r["orbit"]["service_floor_proxy"],"mass_kg":r["program"]["total_mass_kg"],"cost_musd":r["program"]["total_cost_proxy_musd"]})
    return out

def mat_sweep(x:SatcomInput):
    out=[]
    map_pa={"Si":"PA-GaAs-Ka-10W","SiGe":"PA-GaAs-Ka-10W","GaAs":"PA-GaAs-Ka-10W","GaN":"PA-GaN-Ka-20W","SiC":"PA-GaN-Ka-20W"}
    for m in MATERIALS:
        r=satcom(x.model_copy(update={"material":m,"part_pa":map_pa[m]}))
        out.append({"material":m,"eff_pct":r["device"]["pa_eff_pct"],"pa_dc_w":r["device"]["pa_dc_w"],"heat_w":r["device"]["heat_w"],"payload_mass_kg":r["payload"]["mass_kg"],"cost_musd":r["program"]["total_cost_proxy_musd"]})
    return out



class IntegratedInput(ValidatedModel):
    satcom: SatcomInput = SatcomInput()
    beam: BeamInput = BeamInput()
    radiation: RadInput = RadInput()
    payload: PayloadInput = PayloadInput()

def api_integrated(x: IntegratedInput):
    # 1) Semiconductor / link layer
    s = satcom(x.satcom)

    # 2) Propagate shared mission values into beamforming
    beam_in = x.beam.model_copy(update={
        "elements": x.satcom.array_elements,
        "beams": x.satcom.beams,
        "bandwidth_mhz": x.satcom.bandwidth_mhz,
        "available_tops": x.satcom.processor_tops,
    })
    b = beamforming(beam_in)

    # 3) Propagate beamforming power / effective beams into payload
    payload_in = x.payload.model_copy(update={
        "bandwidth_mhz": x.satcom.bandwidth_mhz,
        "beams": int(b["compute"]["effective_beams"]),
        "processor_power_w": b["power"]["processor_w"],
        "converter_power_w": b["power"]["converter_w"],
        "pa_output_w": x.satcom.rf_output_w,
        "pa_efficiency": max(0.05, s["device"]["pa_eff_pct"] / 100.0),
        "frequency_ghz": x.satcom.frequency_ghz,
        "geometry_altitude_km": x.satcom.altitude_km,
        "geometry_total_tx_power_w": x.satcom.rf_output_w,
        "geometry_inclination_deg": x.payload.geometry_inclination_deg,
    })
    p = payload(payload_in)

    # 4) Radiation layer
    r = radiation(x.radiation)

    # 5) Integrated proxies
    # payload() always computes aggregate_scheduled_gbps -- including a genuine 0.0
    # when geometry_channel_enabled is true but no satellite is visible to any user
    # (see payload()'s geometry branch). Treating that computed 0 as "missing" and
    # silently substituting the idealized satcom-link estimate would hide a real
    # zero-capacity result behind a synthetic positive number. Only fall back when
    # the value is truly absent (None), never when it is a legitimate 0.
    payload_cap = p.get("traffic",{}).get("aggregate_scheduled_gbps")
    deterministic_cap = payload_cap if payload_cap is not None else s["link"]["aggregate_gbps"]
    effective_capacity_gbps = deterministic_cap * (r["service"]["electronics_availability_pct"] / 100.0)
    payload_power_combined = max(s["payload"]["power_w"], p["power"]["total_w"])
    payload_mass_combined = max(s["payload"]["mass_kg"], p["system"]["mass_kg"])
    total_mass = max(s["program"]["total_mass_kg"], x.satcom.structure_mass_kg + payload_mass_combined)

    risk_penalty = {"LOW": 0.98, "MEDIUM": 0.90, "HIGH": 0.72}.get(r["risk"]["class"], 0.90)
    service_index = effective_capacity_gbps * risk_penalty

    power_score = max(0.0, min(100.0, 100.0 * x.satcom.bus_power_w / max(x.satcom.bus_power_w, payload_power_combined / max(x.satcom.payload_share, 0.05))))
    mass_score = max(0.0, min(100.0, 100.0 - max(0.0, total_mass - 250.0) * 0.25))
    capacity_score = max(0.0, min(100.0, effective_capacity_gbps * 12.0))
    reliability_score = max(0.0, min(100.0, r["service"]["electronics_availability_pct"]))
    thermal_score = max(0.0, min(100.0, 100.0 - p["power"]["radiator_m2"] * 8.0))

    chain = [
        {"stage":"Semiconductor", "metric":f'{s["device"]["pa_eff_pct"]}% PA eff.', "status":"OK"},
        {"stage":"RF / DBF", "metric":f'{b["compute"]["effective_beams"]} effective beams', "status":"OK" if b["compute"]["margin_x"] >= 1 else "LIMIT"},
        {"stage":"Payload", "metric":f'{p["power"]["total_w"]} W / {p["system"]["mass_kg"]} kg', "status":"OK"},
        {"stage":"Link", "metric":f'{s["link"]["snr_db"]} dB SNR', "status":"OK" if s["link"]["snr_db"] >= 3 else "LIMIT"},
        {"stage":"Radiation", "metric":f'{r["risk"]["class"]} risk', "status":"OK" if r["risk"]["class"] == "LOW" else "WATCH"},
        {"stage":"Service", "metric":f'{effective_capacity_gbps:.2f} Gbps effective', "status":"OK"},
    ]

    bottlenecks = []
    if b["compute"]["margin_x"] < 1:
        bottlenecks.append("Digital beamforming compute")
    if b["power"]["margin_w"] < 0:
        bottlenecks.append("Digital payload power")
    if s["payload"]["spare_w"] < 0:
        bottlenecks.append("Satellite payload power budget")
    if p["power"]["radiator_m2"] > 2.0:
        bottlenecks.append("Thermal radiator size")
    if s["link"]["snr_db"] < 3:
        bottlenecks.append("RF link margin")
    if r["risk"]["class"] == "HIGH":
        bottlenecks.append("Radiation risk")
    if not bottlenecks:
        bottlenecks.append("No dominant bottleneck detected in current proxy model")

    return {
        "satcom": s,
        "beamforming": b,
        "radiation": r,
        "payload": p,
        "integrated": {
            "effective_capacity_gbps": round(effective_capacity_gbps, 3),
            "service_index": round(service_index, 3),
            "payload_power_w": round(payload_power_combined, 1),
            "payload_mass_kg": round(payload_mass_combined, 1),
            "total_mass_kg": round(total_mass, 1),
            "total_cost_proxy_musd": s["program"]["total_cost_proxy_musd"],
            "availability_pct": r["service"]["electronics_availability_pct"],
            "scores": {
                "Power": round(power_score, 1),
                "Mass": round(mass_score, 1),
                "Capacity": round(capacity_score, 1),
                "Reliability": round(reliability_score, 1),
                "Thermal": round(thermal_score, 1),
            },
            "chain": chain,
            "bottlenecks": bottlenecks,
        }
    }



class OptimizeInput(ValidatedModel):
    base: IntegratedInput = IntegratedInput()
    max_total_mass_kg: float = Field(500,gt=0)
    max_payload_power_w: float = Field(1200,gt=0)
    min_effective_capacity_gbps: float = Field(2.0,ge=0)
    min_effective_beams: int = Field(4,ge=0)
    min_availability_pct: float = Field(99.9,ge=0,le=100)
    max_cost_musd: float = Field(100,gt=0)
    allowed_risk: RiskLevel = "MEDIUM"
    objective: OptimizeObjective = "Balanced"

class SensitivityInput(ValidatedModel):
    base: IntegratedInput = IntegratedInput()
    parameter: SensitivityParameter = "rf_output_w"
    low: float = 10
    high: float = 40
    steps: int = Field(7,ge=3,le=25)

    @model_validator(mode="after")
    def _check_range_order(self):
        if not (self.low < self.high):
            raise ValueError(f"low ({self.low}) must be less than high ({self.high})")
        return self

def integrated_calc(x: IntegratedInput):
    s = satcom(x.satcom)
    beam_in = x.beam.model_copy(update={
        "elements": x.satcom.array_elements,
        "beams": x.satcom.beams,
        "bandwidth_mhz": x.satcom.bandwidth_mhz,
        "available_tops": x.satcom.processor_tops,
    })
    b = beamforming(beam_in)
    payload_in = x.payload.model_copy(update={
        "bandwidth_mhz": x.satcom.bandwidth_mhz,
        "beams": int(b["compute"]["effective_beams"]),
        "processor_power_w": b["power"]["processor_w"],
        "converter_power_w": b["power"]["converter_w"],
        "pa_output_w": x.satcom.rf_output_w,
        "pa_efficiency": max(0.05, s["device"]["pa_eff_pct"]/100),
        "frequency_ghz": x.satcom.frequency_ghz,
        "geometry_altitude_km": x.satcom.altitude_km,
        "geometry_total_tx_power_w": x.satcom.rf_output_w,
        "geometry_inclination_deg": x.payload.geometry_inclination_deg,
    })
    p = payload(payload_in)
    r = radiation(x.radiation)

    # See api_integrated()'s matching comment: a computed 0 (e.g. no visible
    # satellite) must never be silently replaced by the idealized link fallback.
    payload_cap = p.get("traffic",{}).get("aggregate_scheduled_gbps")
    deterministic_cap = payload_cap if payload_cap is not None else s["link"]["aggregate_gbps"]
    eff_cap = deterministic_cap * (r["service"]["electronics_availability_pct"]/100)
    payload_power = max(s["payload"]["power_w"], p["power"]["total_w"])
    payload_mass = max(s["payload"]["mass_kg"], p["system"]["mass_kg"])
    total_mass = max(s["program"]["total_mass_kg"], x.satcom.structure_mass_kg + payload_mass)
    risk_penalty = {"LOW":0.98,"MEDIUM":0.90,"HIGH":0.72}.get(r["risk"]["class"],0.90)
    service_index = eff_cap*risk_penalty

    return {
        "satcom":s,"beamforming":b,"payload":p,"radiation":r,
        "integrated":{
            "effective_capacity_gbps":round(eff_cap,3),
            "payload_power_w":round(payload_power,1),
            "payload_mass_kg":round(payload_mass,1),
            "total_mass_kg":round(total_mass,1),
            "total_cost_proxy_musd":s["program"]["total_cost_proxy_musd"],
            "availability_pct":r["service"]["electronics_availability_pct"],
            "service_index":round(service_index,3),
            "effective_beams":b["compute"]["effective_beams"],
            "risk_class":r["risk"]["class"],
        }
    }

def api_optimize(x: OptimizeInput):
    risk_rank={"LOW":0,"MEDIUM":1,"HIGH":2}
    allowed_rank=risk_rank.get(x.allowed_risk,1)
    materials=["GaAs","GaN"]; processors=["FPGA","ASIC"]
    altitudes=[500,888,1280]; beams_list=[4,8,12,16]
    rf_outputs=[10,20,30,40]; elements_list=[128,256,512]; bw_list=[50,100,200]

    candidates=batched_design_grid(materials,processors,altitudes,beams_list,rf_outputs,elements_list,bw_list)
    base_dump=x.base.model_dump()
    work=[{"base":base_dump,"candidate":c} for c in candidates]
    evaluated=parallel_map(optimize_case_worker,work,chunksize=24)

    rows=[]
    for i in evaluated:
        feasible=(
            i["total_mass_kg"]<=x.max_total_mass_kg and
            i["payload_power_w"]<=x.max_payload_power_w and
            i["effective_capacity_gbps"]>=x.min_effective_capacity_gbps and
            i["effective_beams"]>=x.min_effective_beams and
            i["availability_pct"]>=x.min_availability_pct and
            i["total_cost_proxy_musd"]<=x.max_cost_musd and
            risk_rank.get(i["risk_class"],2)<=allowed_rank
        )
        if not feasible: continue
        mass_n=i["total_mass_kg"]/max(x.max_total_mass_kg,1)
        power_n=i["payload_power_w"]/max(x.max_payload_power_w,1)
        cost_n=i["total_cost_proxy_musd"]/max(x.max_cost_musd,1)
        cap_n=x.min_effective_capacity_gbps/max(i["effective_capacity_gbps"],1e-6)
        if x.objective=="Lowest Cost":
            score=cost_n*.55+mass_n*.15+power_n*.15+cap_n*.15
        elif x.objective=="Highest Capacity":
            score=cap_n*.55+power_n*.15+mass_n*.15+cost_n*.15
        elif x.objective=="Lowest Mass":
            score=mass_n*.55+power_n*.15+cost_n*.15+cap_n*.15
        else:
            score=(mass_n+power_n+cost_n+cap_n)/4
        rows.append({
            "score":round(score,4),"material":i["material"],"processor":i["processor"],
            "altitude_km":i["altitude_km"],"beams":i["beams"],"elements":i["elements"],
            "bandwidth_mhz":i["bandwidth_mhz"],"rf_output_w":i["rf_output_w"],
            "capacity_gbps":i["effective_capacity_gbps"],"mass_kg":i["total_mass_kg"],
            "payload_power_w":i["payload_power_w"],"cost_musd":i["total_cost_proxy_musd"],
            "availability_pct":i["availability_pct"],"risk":i["risk_class"]
        })
    rows=sorted(rows,key=lambda z:z["score"])[:20]
    return {"count":len(rows),"evaluated":len(candidates),"parallel":True,"results":rows,
        "note":"Batch evaluation uses Fast screening (no full waveform sampling, no per-user "
               "geometry/visibility masking) across the full design grid for performance. "
               "Re-run a shortlisted design through /api/integrated with "
               "geometry_channel_enabled=true for a full mission-geometry-aware result."}

def api_sensitivity(x: SensitivityInput):
    steps=max(3,min(25,x.steps))
    vals=[x.low+(x.high-x.low)*i/(steps-1) for i in range(steps)]
    rows=[]
    for v in vals:
        sat=x.base.satcom
        beam=x.base.beam
        rad=x.base.radiation
        payload_in=x.base.payload.model_copy(update={"analysis_mode":"Fast","hpa_samples":256,"geometry_channel_enabled":False})
        if x.parameter=="rf_output_w":
            sat=sat.model_copy(update={"rf_output_w":v})
        elif x.parameter=="bandwidth_mhz":
            sat=sat.model_copy(update={"bandwidth_mhz":v})
            beam=beam.model_copy(update={"bandwidth_mhz":v})
            payload_in=payload_in.model_copy(update={"bandwidth_mhz":v})
        elif x.parameter=="beams":
            sat=sat.model_copy(update={"beams":int(round(v))})
            beam=beam.model_copy(update={"beams":int(round(v))})
            payload_in=payload_in.model_copy(update={"beams":int(round(v))})
        elif x.parameter=="elements":
            sat=sat.model_copy(update={"array_elements":int(round(v))})
            beam=beam.model_copy(update={"elements":int(round(v))})
        elif x.parameter=="altitude_km":
            sat=sat.model_copy(update={"altitude_km":v})
        elif x.parameter=="shielding_mm_al":
            rad=rad.model_copy(update={"shielding_mm_al":v})
        case=IntegratedInput(satcom=sat,beam=beam,radiation=rad,payload=payload_in)
        r=integrated_calc(case)["integrated"]
        rows.append({"x":round(v,4),**r})
    return {"parameter":x.parameter,"rows":rows,
        "note":"Sensitivity sweep uses Fast screening (no full waveform sampling, no per-user "
               "geometry/visibility masking) across every step for performance. Re-run a step "
               "of interest through /api/integrated with geometry_channel_enabled=true for a "
               "full mission-geometry-aware result."}

def api_report_summary(x: IntegratedInput):
    r=integrated_calc(x)
    i=r["integrated"]
    b=r["beamforming"]
    p=r["payload"]
    rad=r["radiation"]
    bullets=[
        f'통합 시나리오의 실효 서비스 용량은 약 {i["effective_capacity_gbps"]} Gbps이다.',
        f'총 질량 프록시는 {i["total_mass_kg"]} kg, 탑재체 전력은 {i["payload_power_w"]} W이다.',
        f'디지털 빔포밍은 요청 빔 중 {i["effective_beams"]}개를 유효하게 처리한다.',
        f'방사선 위험 등급은 {i["risk_class"]}, 전자장비 가용도는 {i["availability_pct"]}%이다.',
        f'RF 탑재체 열부하는 {p["power"]["heat_w"]} W, radiator 면적 프록시는 {p["power"]["radiator_m2"]} m²이다.'
    ]
    return {"headline":"Space Deep Tech Center V0.6 Integrated Design Summary","bullets":bullets}



import random
from statistics import mean

REGIONS = {
    "Korea": {"lat_deg": 36.3, "lon_deg": 127.8, "label": "Korea"},
    "UAE": {"lat_deg": 24.4, "lon_deg": 54.4, "label": "UAE"},
    "Southeast Asia": {"lat_deg": 10.0, "lon_deg": 106.8, "label": "Southeast Asia"},
}

class CoverageInput(ValidatedModel):
    altitude_km: float = Field(1280,ge=ALTITUDE_KM_MIN,le=ALTITUDE_KM_MAX)
    inclination_deg: float = Field(42,ge=0,le=180)
    planes: int = Field(16, ge=1, le=60)
    sats_per_plane: int = Field(8, ge=1, le=60)
    min_elevation_deg: float = Field(20,ge=0,le=90)
    target_min_visible: int = Field(1,ge=1)
    walker_f: int = Field(1,ge=0)
    duration_hours: float = Field(24, ge=0.01, le=168)
    time_step_sec: float = Field(120, ge=5, le=3600)

    @model_validator(mode="after")
    def _check_walker_phasing_feasible(self):
        if self.walker_f >= self.planes:
            raise ValueError(
                f"walker_f ({self.walker_f}) must be less than planes ({self.planes}) "
                "for a valid Walker Delta-pattern phasing (0 <= F < planes)"
            )
        return self

class MonteCarloInput(ValidatedModel):
    base: IntegratedInput = IntegratedInput()
    runs: int = Field(500, ge=1, le=5000)
    seed: int = 42
    rf_output_sigma_pct: float = Field(5,ge=0)
    pa_eff_sigma_pct: float = Field(6,ge=0)
    loss_sigma_db: float = Field(0.8,ge=0)
    bandwidth_sigma_pct: float = Field(5,ge=0)
    processor_tops_sigma_pct: float = Field(8,ge=0)
    tid_sigma_pct: float = Field(20,ge=0)
    seu_sigma_pct: float = Field(25,ge=0)
    mass_sigma_pct: float = Field(4,ge=0)
    cost_sigma_pct: float = Field(8,ge=0)
    capacity_threshold_gbps: float = Field(2.0,ge=0)
    max_power_w: float = Field(1200,gt=0)
    max_mass_kg: float = Field(500,gt=0)

def _walker_satellite_positions_ecef(x: CoverageInput, t_s: float):
    a=R_EARTH+x.altitude_km
    inc=radians(x.inclination_deg)
    n=sqrt(MU_EARTH/a**3)
    theta_e=OMEGA_EARTH*t_s
    total=max(1,x.planes*x.sats_per_plane)
    f=x.walker_f % max(1,x.planes)
    out=[]
    for p in range(x.planes):
        raan=2*pi*p/x.planes
        for s in range(x.sats_per_plane):
            u0=2*pi*(s/x.sats_per_plane + f*p/total)
            u=u0+n*t_s
            cu,su=cos(u),sin(u)
            cO,sO=cos(raan),sin(raan)
            ci,si=cos(inc),sin(inc)
            # ECI for circular orbit: R3(Ω)R1(i)[a cos u, a sin u, 0]
            xeci=a*(cO*cu-sO*su*ci)
            yeci=a*(sO*cu+cO*su*ci)
            zeci=a*(su*si)
            # ECI -> ECEF through Earth rotation
            ct,st=cos(theta_e),sin(theta_e)
            xe=ct*xeci+st*yeci
            ye=-st*xeci+ct*yeci
            out.append((xe,ye,zeci))
    return out

def _ground_ecef(lat_deg: float, lon_deg: float):
    lat,lon=radians(lat_deg),radians(lon_deg)
    cl=cos(lat)
    u=(cl*cos(lon),cl*sin(lon),sin(lat))
    return (R_EARTH*u[0],R_EARTH*u[1],R_EARTH*u[2]),u

def _elevation_deg(sat, ground, zenith):
    dx=sat[0]-ground[0]; dy=sat[1]-ground[1]; dz=sat[2]-ground[2]
    rng=sqrt(dx*dx+dy*dy+dz*dz)
    if rng<=0:return -90.0
    sinel=(dx*zenith[0]+dy*zenith[1]+dz*zenith[2])/rng
    return degrees(math.asin(max(-1.0,min(1.0,sinel))))

def _longest_outage_sec(ok_series, step_s):
    if not ok_series:return 0.0
    longest=cur=0
    for ok in ok_series:
        if ok: cur=0
        else:
            cur+=1
            longest=max(longest,cur)
    return longest*step_s

def _longest_outage_duration_s(times, ok):
    """
    Longest outage duration (seconds), as the elapsed time between the first and
    last bad (not-ok) sample of the longest run of consecutive bad samples, using
    the actual sample times rather than assuming a fixed step width.

    A run of N consecutive bad samples spans original-array indices
    [start, start+N-1]; its elapsed duration is times[start+N-1] - times[start].
    Multiplying the sample *count* N by the nominal step instead (the previous
    approach) credits one extra full step-width beyond the last observed-bad
    instant, over-reporting every outage by one step.
    """
    times=np.asarray(times,dtype=float)
    ok=np.asarray(ok,dtype=bool)
    if times.size==0:
        return 0.0
    bad=(~ok).astype(int)
    padded=np.r_[0,bad,0]
    starts=np.where(np.diff(padded)==1)[0]
    ends=np.where(np.diff(padded)==-1)[0]
    if len(starts)==0:
        return 0.0
    # `ends` (from the padded array) is one past the last bad index in the
    # original array, so times[ends-1] is the last bad sample's actual time.
    return float((times[ends-1]-times[starts]).max())

def _coverage_proxy(x: CoverageInput):
    total=max(1,x.planes*x.sats_per_plane)
    period=orbital_period_s(x.altitude_km)
    psi_deg,foot_r,foot_a=footprint(x.altitude_km,x.min_elevation_deg)
    step=max(20.0,min(1800.0,x.time_step_sec))
    # Respect the requested analysis window exactly. Forcing duration up to at
    # least `step` (the previous `max(step, ...)`) silently extended the analyzed
    # period past what was asked whenever the time step exceeded the requested
    # duration_hours. The window end is now always the requested duration itself.
    requested_duration=max(0.0,min(7*24*3600.0,x.duration_hours*3600.0))
    n_samples=max(2,int(np.floor(requested_duration/step))+1)
    times=np.linspace(0,requested_duration,n_samples)
    rows=[]
    for key,reg in REGIONS.items():
        v=regional_visibility_times(
            x.altitude_km,x.inclination_deg,x.planes,x.sats_per_plane,x.walker_f,
            times,x.min_elevation_deg,key
        )
        counts=np.asarray(v["counts"])
        ok=counts>=x.target_min_visible
        avail=100*ok.mean()
        longest=_longest_outage_duration_s(times,ok)
        rows.append({
            "region":key,"latitude_deg":reg["lat_deg"],"longitude_deg":reg["lon_deg"],
            "availability_pct":round(float(avail),3),"continuity_pct":round(float(avail),3),
            "mean_visible_proxy":round(float(counts.mean()),3),"max_visible":int(counts.max()),
            "longest_outage_min":round(float(longest/60),2)
        })
    return {
      "total_sats":total,"planes":x.planes,"sats_per_plane":x.sats_per_plane,
      "period_min":round(period/60,2),"footprint_radius_km":round(foot_r,1),
      "footprint_half_angle_deg":round(psi_deg,2),
      "mean_global_overlap_proxy":round(total*foot_a/(4*pi*R_EARTH**2),2),
      "regions":rows,
      "physics":{"orbit":"vectorized two-body circular Walker propagation","earth_rotation":"sidereal Earth rotation","visibility":"topocentric elevation threshold"},
      "note":"V0.5 vectorizes the full time×satellite propagation. J2, drag, eccentricity and refraction remain outside this model."
    }

def api_coverage(x: CoverageInput):
    return _coverage_proxy(x)

def api_montecarlo(x: MonteCarloInput):
    runs=max(100,min(5000,x.runs))
    means={"rf":x.base.satcom.rf_output_w,"bw":x.base.satcom.bandwidth_mhz,"tops":x.base.satcom.processor_tops,
           "tid":x.base.radiation.tid_env_krad_yr,"seu":x.base.radiation.seu_rate_device_day}
    sigmas={"rf":means["rf"]*x.rf_output_sigma_pct/100,"bw":means["bw"]*x.bandwidth_sigma_pct/100,
            "tops":means["tops"]*x.processor_tops_sigma_pct/100,"tid":means["tid"]*x.tid_sigma_pct/100,
            "seu":means["seu"]*x.seu_sigma_pct/100}
    rng=np.random.default_rng(x.seed)
    draws=monte_carlo_draws(rng,runs,means,sigmas)
    loss=np.maximum(0,rng.normal(x.base.satcom.losses_db,x.loss_sigma_db,runs))
    mf=np.maximum(.1,rng.normal(1.0,x.mass_sigma_pct/100,runs))
    cf=np.maximum(.1,rng.normal(1.0,x.cost_sigma_pct/100,runs))
    # PA efficiency perturbation: a multiplicative factor around 1.0 (neutral).
    # sigma=0 makes rng.normal(1.0, 0, runs) return exactly 1.0 for every run, so
    # this is bit-for-bit identical to the pre-existing (unperturbed) baseline
    # when pa_eff_sigma_pct=0. It flows into satcom()'s PA efficiency, which
    # drives pa_dc_w, heat_w and (via the radiator sizing and payload mass roll-up
    # in satcom()/payload()) mass_kg for every downstream consumer of this draw.
    pa_eff_mult=np.maximum(.05,rng.normal(1.0,x.pa_eff_sigma_pct/100,runs))

    base_dump=x.base.model_dump()
    work=[]
    for i in range(runs):
        work.append({"base":base_dump,"draw":{
            "rf":max(.1,float(draws["rf"][i])),"bw":max(1.0,float(draws["bw"][i])),
            "tops":max(.05,float(draws["tops"][i])),"tid":max(0.0,float(draws["tid"][i])),
            "seu":max(0.0,float(draws["seu"][i])),"loss":float(loss[i]),
            "mass_factor":float(mf[i]),"cost_factor":float(cf[i]),
            "pa_eff_mult":float(pa_eff_mult[i])
        }})
    rows=parallel_map(monte_carlo_case_worker,work,chunksize=max(8,runs//64))
    for r in rows:
        r["success"]=(r["capacity_gbps"]>=x.capacity_threshold_gbps and r["power_w"]<=x.max_power_w and r["mass_kg"]<=x.max_mass_kg)

    metrics={}
    for key in ["capacity_gbps","power_w","mass_kg","cost_musd"]:
        vals=np.asarray([r[key] for r in rows],float)
        q=np.quantile(vals,[.1,.5,.9])
        metrics[key]={"p10":round(float(q[0]),3),"p50":round(float(q[1]),3),"p90":round(float(q[2]),3),"mean":round(float(vals.mean()),3)}
    success_pct=100*np.mean([r["success"] for r in rows])
    return {
        "runs":runs,"seed":x.seed,"parallel":True,
        "success_probability_pct":round(float(success_pct),2),
        "metrics":metrics,"samples":rows[:min(1000,len(rows))],
        "note":"V0.5 vectorizes random draws and evaluates cases through a bounded process pool. Full waveform/geometry is reserved for interactive confirmation."
    }

def api_coverage_sweep(x: CoverageInput):
    out=[]
    for planes in [4,8,12,16,20]:
        for spp in [4,8,12,16]:
            r=_coverage_proxy(x.model_copy(update={"planes":planes,"sats_per_plane":spp,"duration_hours":8,"time_step_sec":900}))
            avg=sum(z["availability_pct"] for z in r["regions"])/len(r["regions"])
            min_av=min(z["availability_pct"] for z in r["regions"])
            out.append({
                "planes":planes,"sats_per_plane":spp,"total_sats":planes*spp,
                "avg_region_availability_pct":round(avg,2),
                "min_region_availability_pct":round(min_av,2),
            })
    return out


def api_theory():
    return {
        "physics_core":[
            {"area":"Orbit","equation":"T = 2π√(a³/μ), v = √(μ/a)","status":"physics"},
            {"area":"Walker visibility","equation":"two-body circular propagation + Earth rotation + topocentric elevation","status":"physics"},
            {"area":"Free-space link","equation":"Pr = Pt Gt Gr (λ/4πR)² / L","status":"physics"},
            {"area":"Noise","equation":"N = kTB, Te = T0(F-1)","status":"physics"},
            {"area":"Capacity","equation":"C = B log2(1+SNR/Γ)","status":"physics"},
            {"area":"Antenna aperture","equation":"G = η(πD/λ)²","status":"physics"},
            {"area":"Thermal radiator","equation":"Q = εσAF(T⁴-Tspace⁴)","status":"physics"},
            {"area":"Beam phase error","equation":"ηcoh ≈ exp(-σφ²)","status":"physics"},
        ],
        "engineering_models":[
            "component mass and cost scaling",
            "ADC / FPGA / ASIC power scaling",
            "radiation shielding attenuation and mitigation factors",
            "program launch-cost proxy",
            "some subsystem base masses and fixed overhead powers"
        ]
    }



def api_propagation(x: PropagationInput):
    k,alpha,gamma=rain_specific_attenuation_p838(
        x.frequency_ghz,x.rain_rate_mm_h,x.elevation_deg,x.polarization,x.polarization_tilt_deg
    )
    geom=geometric_rain_path_km(x.elevation_deg,x.rain_height_km,x.station_height_km)
    eff=geom*max(0.0,min(1.0,x.path_reduction_factor))
    att=gamma*eff
    return {
        "k":round(k,7),"alpha":round(alpha,5),"specific_attenuation_db_km":round(gamma,4),
        "geometric_rain_path_km":round(geom,3),"effective_rain_path_km":round(eff,3),
        "rain_attenuation_db":round(att,3),
        "physics":"ITU-R P.838-3 gamma_R = k R^alpha with selected Table-5 coefficient interpolation.",
        "boundary":"Rain-path geometry is explicit; this is not the full ITU-R P.618-14 statistical exceedance procedure."
    }

def api_poisson_device(x: PoissonDeviceInput):
    if x.model.lower().startswith("poisson-b") or x.model.lower().startswith("nonlinear"):
        return solve_poisson_boltzmann_1d(x)
    return solve_poisson_1d(x)

def api_pass_timeline(x: PassTimelineInput):
    reg=REGIONS.get(x.region,REGIONS["Korea"])
    cov=CoverageInput(
        altitude_km=x.altitude_km,inclination_deg=x.inclination_deg,planes=x.planes,
        sats_per_plane=x.sats_per_plane,min_elevation_deg=x.min_elevation_deg,
        target_min_visible=1,walker_f=x.walker_f,duration_hours=x.duration_hours,time_step_sec=x.time_step_sec
    )
    g,z=_ground_ecef(reg["lat_deg"],reg["lon_deg"])
    step=max(10.0,min(900.0,x.time_step_sec))
    # Respect the requested analysis window exactly -- do not extend it to fit a
    # whole number of steps when the step is larger than the requested duration
    # (see _coverage_proxy for the matching fix and rationale).
    requested_duration=max(0.0,min(48*3600.0,x.duration_hours*3600.0))
    n_samples=max(2,int(np.floor(requested_duration/step))+1)
    times=np.linspace(0,requested_duration,n_samples)
    rows=[]
    for t in times:
        t=float(t)
        sats=_walker_satellite_positions_ecef(cov,t)
        sats2=_walker_satellite_positions_ecef(cov,t+1.0)
        visible=[]
        for idx,(sat,sat2) in enumerate(zip(sats,sats2)):
            el=_elevation_deg(sat,g,z)
            if el>=x.min_elevation_deg:
                def rg(s):
                    dx=s[0]-g[0];dy=s[1]-g[1];dz=s[2]-g[2]
                    return sqrt(dx*dx+dy*dy+dz*dz)
                r0=rg(sat); r1=rg(sat2)
                rr=(r1-r0)*1000.0 # m/s over 1 sec
                # positive range-rate means receding -> negative received Doppler convention
                doppler_hz=-(20e9)*rr/C_LIGHT
                visible.append((idx,el,r0,doppler_hz))
        if visible:
            best=max(visible,key=lambda q:q[1])
            maxel=best[1]; minrange=min(v[2] for v in visible); bestdop=best[3]
        else:
            maxel=-90.0;minrange=None;bestdop=0.0
        rows.append({
            "time_min":round(t/60,3),"visible_count":len(visible),"max_elevation_deg":round(maxel,3),
            "min_range_km":round(minrange,3) if minrange is not None else None,
            "best_doppler_khz":round(bestdop/1e3,3)
        })
    return {
        "region":x.region,"frequency_assumed_ghz_for_doppler":20.0,"rows":rows,
        "physics":"Time-stepped Walker circular orbit + Earth rotation; Doppler from finite-difference range rate ΔR/Δt and Δf/f = -vr/c.",
        "note":"J2, drag, eccentricity and atmospheric refraction are omitted."
    }


PHYSICS_REGISTRY = [
 {"id":"orbit.kepler.circular","domain":"Orbit","equation":"T=2π√(a³/μ), v=√(μ/a)","level":"fundamental","version":"1.0"},
 {"id":"rf.friis","domain":"RF Link","equation":"Pr=PtGtGr(λ/4πR)²/L","level":"fundamental","version":"1.0"},
 {"id":"rf.noise.ktb","domain":"RF Link","equation":"N=kTB","level":"fundamental","version":"1.0"},
 {"id":"info.shannon","domain":"Information","equation":"C=B log2(1+SNR/Γ)","level":"fundamental+gap","version":"1.0"},
 {"id":"thermal.stefan","domain":"Thermal","equation":"Q=εσAF(T⁴-Tspace⁴)","level":"fundamental","version":"1.0"},
 {"id":"semiconductor.poisson","domain":"Device","equation":"∇²φ=-ρ/ε","level":"fundamental","version":"1.0"},
 {"id":"semiconductor.poisson_boltzmann","domain":"Device","equation":"∇²φ=-q(Ndop+p-n)/ε","level":"fundamental+Boltzmann","version":"1.0"},
 {"id":"array.phase_error","domain":"Beamforming","equation":"ηcoh≈exp(-σφ²)","level":"analytical","version":"1.0"},
 {"id":"rain.p838","domain":"Propagation","equation":"γR=kR^α","level":"ITU recommendation","version":"1.0"},
 {"id":"hpa.rapp","domain":"RF Payload","equation":"y=x/[1+(x/Asat)^(2p)]^(1/2p)","level":"behavioral","version":"1.0"},
 {"id":"payload.flex_resource","domain":"RF Payload","equation":"beam hopping/reuse scheduler","level":"engineering","version":"1.1"},
 {"id":"payload.sinr.matrix","domain":"RF Payload","equation":"SINR_i=|h_i w_i|²/(Σj≠i|h_i w_j|²+N)","level":"signal-domain","version":"1.1"},
 {"id":"payload.precoding.rzf","domain":"RF Payload","equation":"W=Hᴴ(HHᴴ+λI)⁻¹","level":"linear algebra / signal processing","version":"1.1"},
 {"id":"payload.hpa.sampled","domain":"RF Payload","equation":"sampled complex-envelope Rapp → EVM / FFT spectral-regrowth proxy","level":"behavioral signal model","version":"1.2"},
 {"id":"payload.channel.geometry","domain":"RF Payload","equation":"H_ub ∝ √(Gt(θub)Gr) λ/(4πR_u) exp(-jkR_u)","level":"physics-grounded channel","version":"1.2"},
 {"id":"payload.beam.gaussian","domain":"Antenna","equation":"G(θ)/G0=exp[-4 ln2(θ/HPBW)²]","level":"analytical beam approximation","version":"1.2"},
 {"id":"payload.scheduler.throughput","domain":"RF Payload","equation":"R_u=duty_u·B log2(1+SINR_u/Γ)","level":"signal+resource model","version":"1.2"},
 {"id":"numerics.analysis_mode","domain":"Numerics","equation":"Full FFT physics vs Fast screening approximation","level":"computational strategy","version":"1.3"},
 {"id":"numerics.memoization","domain":"Numerics","equation":"LRU caching for repeated scalar orbit/link and Walker states","level":"computational strategy","version":"1.3"}
]
def api_physics_registry():
    return {"core_version":"1.0","count":len(PHYSICS_REGISTRY),"registry":PHYSICS_REGISTRY}


def api_performance():
    return {
        "version":"0.5.0",
        "caches":{
            "walker":_walker_ecef_cached.cache_info()._asdict(),
            "slant":_cached_slant_range.cache_info()._asdict(),
            "footprint":_cached_footprint.cache_info()._asdict(),
            "fspl":_cached_fspl.cache_info()._asdict(),
            "orbit_scalar":_cached_orbit_scalar.cache_info()._asdict(),
            "antenna_gain":_cached_antenna_gain.cache_info()._asdict(),
        },
        "modes":{
            "interactive_payload":"Full",
            "optimizer":"Fast + geometry fallback disabled",
            "monte_carlo":"Fast + geometry fallback disabled",
            "sensitivity":"Fast + geometry fallback disabled"
        }
    }

def health(): return {"status":"ok","version":"0.5.0","labs":9}