import numpy as np
from functools import lru_cache
from math import pi, sqrt
from physics.core import R_EARTH, MU_EARTH, OMEGA_EARTH

REGIONS={
 "Korea":{"lat_deg":36.3,"lon_deg":127.8},
 "UAE":{"lat_deg":24.4,"lon_deg":54.4},
 "Southeast Asia":{"lat_deg":10.0,"lon_deg":106.8},
}

def ground_ecef(lat_deg,lon_deg):
    lat=np.radians(lat_deg); lon=np.radians(lon_deg)
    u=np.array([np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)])
    return R_EARTH*u,u

def user_grid(region,users,radius_km):
    reg=REGIONS.get(region,REGIONS["Korea"])
    n=max(1,min(128,int(users)))
    i=np.arange(n)
    rr=radius_km*np.sqrt((i+.5)/n)
    bearing=i*(pi*(3-sqrt(5)))
    lat0=np.radians(reg["lat_deg"]); lon0=np.radians(reg["lon_deg"])
    d=rr/R_EARTH
    lat=np.arcsin(np.sin(lat0)*np.cos(d)+np.cos(lat0)*np.sin(d)*np.cos(bearing))
    lon=lon0+np.arctan2(np.sin(bearing)*np.sin(d)*np.cos(lat0),np.cos(d)-np.sin(lat0)*np.sin(lat))
    return np.column_stack([np.degrees(lat),((np.degrees(lon)+180)%360)-180])

def latlon_to_ecef(latlon):
    a=np.asarray(latlon,float)
    lat=np.radians(a[:,0]); lon=np.radians(a[:,1]); cl=np.cos(lat)
    return np.column_stack([R_EARTH*cl*np.cos(lon),R_EARTH*cl*np.sin(lon),R_EARTH*np.sin(lat)])

def walker_positions_times(altitude_km,inclination_deg,planes,sats_per_plane,walker_f,times_s):
    """Vectorized time x satellite x xyz Walker propagation."""
    times=np.asarray(times_s,float)
    a=R_EARTH+altitude_km
    inc=np.radians(inclination_deg)
    n=sqrt(MU_EARTH/a**3)
    p=np.arange(planes)[:,None]
    s=np.arange(sats_per_plane)[None,:]
    total=max(1,planes*sats_per_plane)
    raan=2*pi*p/planes
    u0=2*pi*(s/sats_per_plane+(walker_f%max(1,planes))*p/total)
    u=u0[None,:,:]+n*times[:,None,None]
    cu=np.cos(u); su=np.sin(u)
    cO=np.cos(raan)[None,:,:]; sO=np.sin(raan)[None,:,:]
    ci=np.cos(inc); si=np.sin(inc)
    xeci=a*(cO*cu-sO*su*ci)
    yeci=a*(sO*cu+cO*su*ci)
    zeci=a*(su*si)
    th=OMEGA_EARTH*times[:,None,None]
    ct=np.cos(th); st=np.sin(th)
    xe=ct*xeci+st*yeci
    ye=-st*xeci+ct*yeci
    xyz=np.stack([xe,ye,zeci],axis=-1)
    return xyz.reshape(len(times),planes*sats_per_plane,3)

@lru_cache(maxsize=128)
def walker_single_cached(altitude_km,inclination_deg,planes,sats_per_plane,walker_f,t_s):
    return walker_positions_times(float(altitude_km),float(inclination_deg),int(planes),int(sats_per_plane),int(walker_f),np.array([float(t_s)]))[0]

def elevation_matrix(sats_xyz,ground_xyz,zenith):
    los=sats_xyz-ground_xyz
    rng=np.linalg.norm(los,axis=-1)
    sinel=np.einsum("...j,j->...",los,zenith)/np.maximum(rng,1e-12)
    return np.degrees(np.arcsin(np.clip(sinel,-1,1))),rng

def regional_visibility_times(altitude_km,inclination_deg,planes,spp,walker_f,times_s,min_elev,region):
    reg=REGIONS[region]
    g,z=ground_ecef(reg["lat_deg"],reg["lon_deg"])
    sats=walker_positions_times(altitude_km,inclination_deg,planes,spp,walker_f,times_s)
    elev,rng=elevation_matrix(sats,g,z)
    visible=elev>=min_elev
    return {
      "counts":visible.sum(axis=1),
      "max_elevation":elev.max(axis=1),
      "min_range":np.where(visible,rng,np.inf).min(axis=1),
      "elevation":elev,"range":rng,"visible":visible
    }
