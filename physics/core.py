from math import pi, sqrt, log10, log2, sin, cos, radians, degrees, acos
from functools import lru_cache

R_EARTH = 6371.0
MU_EARTH = 398600.4418
OMEGA_EARTH = 7.2921159e-5
C_LIGHT = 299792458.0
K_BOLTZ = 1.380649e-23
SIGMA_SB = 5.670374419e-8
T_SPACE = 3.0
K_DBW = 10*log10(K_BOLTZ)

def db_to_lin(x): return 10**(x/10)
def lin_to_db(x): return 10*log10(max(x,1e-18))
def dbw(w): return 10*log10(max(w,1e-18))
def fspl(freq_ghz,dist_km): return 92.45+20*log10(freq_ghz)+20*log10(dist_km)

def slant_range(alt,elev):
    e=radians(elev)
    return sqrt((R_EARTH+alt)**2-(R_EARTH*cos(e))**2)-R_EARTH*sin(e)

def footprint(alt,elev):
    e=radians(elev)
    val=max(-1,min(1,(R_EARTH/(R_EARTH+alt))*cos(e)))
    psi=max(0,acos(val)-e)
    radius=R_EARTH*psi
    area=2*pi*R_EARTH**2*(1-cos(psi))
    return degrees(psi),radius,area

def orbital_period_s(altitude_km):
    a=R_EARTH+altitude_km
    return 2*pi*sqrt(a**3/MU_EARTH)

def orbital_speed_km_s(altitude_km):
    return sqrt(MU_EARTH/(R_EARTH+altitude_km))

def antenna_gain_dbi(diameter_m,efficiency,frequency_ghz):
    lam=C_LIGHT/(frequency_ghz*1e9)
    return lin_to_db(max(1e-15,efficiency*(pi*diameter_m/lam)**2))

def noise_temp_from_nf_db(nf_db,t0_k=290.0):
    return t0_k*(db_to_lin(nf_db)-1)

def thermal_radiator_area(heat_w,temp_k,emissivity,view_factor,margin_pct=0):
    eps=max(.01,min(1.0,emissivity))
    vf=max(.01,min(1.0,view_factor))
    flux=eps*SIGMA_SB*vf*max(1.0,temp_k**4-T_SPACE**4)
    return max(0.0,heat_w*(1+margin_pct/100)/flux)

@lru_cache(maxsize=4096)
def cached_slant_range(alt,elev): return slant_range(float(alt),float(elev))
@lru_cache(maxsize=4096)
def cached_footprint(alt,elev): return footprint(float(alt),float(elev))
@lru_cache(maxsize=4096)
def cached_fspl(f,r): return fspl(float(f),float(r))
@lru_cache(maxsize=4096)
def cached_orbit(alt): return orbital_period_s(float(alt)),orbital_speed_km_s(float(alt))
@lru_cache(maxsize=1024)
def cached_gain(d,e,f): return antenna_gain_dbi(float(d),float(e),float(f))
