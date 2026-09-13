import numpy as np
from math import pi, log10, sqrt
from physics.core import C_LIGHT, db_to_lin

def gaussian_gain(theta_deg,peak_gain_dbi,hpbw_deg):
    th=np.asarray(theta_deg,float); h=max(.05,hpbw_deg)
    return db_to_lin(peak_gain_dbi)*np.exp(-4*np.log(2)*(th/h)**2)

def precoder(H,method="RZF",lam=.1):
    H=np.asarray(H,complex)
    if H.size==0:return np.zeros((0,0),complex)
    if method.upper()=="MRT":
        W=H.conj().T
    else:
        G=H@H.conj().T
        reg=max(1e-9,lam) if method.upper()=="RZF" else 1e-9
        W=H.conj().T@np.linalg.pinv(G+reg*np.eye(G.shape[0]))
    return W/np.maximum(np.linalg.norm(W,axis=0),1e-15)[None,:]

def sinr(H,W,total_power_w,noise_dbm,weights=None):
    H=np.asarray(H,complex); W=np.asarray(W,complex)
    if H.size==0 or W.size==0:return np.array([])
    streams=W.shape[1]
    if weights is None: weights=np.ones(streams)/streams
    else:
        weights=np.asarray(weights,float); weights/=max(weights.sum(),1e-30)
    p=total_power_w*weights
    HW=H@W
    sig=p[:len(HW)]*np.abs(np.diag(HW[:streams,:streams]))**2
    power=np.abs(HW[:len(sig),:])**2*p[None,:]
    interf=power.sum(axis=1)-sig
    noise=10**((noise_dbm-30)/10)
    return 10*np.log10(np.maximum(sig/(interf+noise),1e-30))

def ofdm_rapp(order=16,samples=2048,papr_db=8,obo_db=3,rapp_p=3):
    n=max(512,min(16384,int(samples))); nfft=256; occ=96; os=4
    nsym=int(np.ceil(n/(nfft*os)))
    m=int(round(np.sqrt(max(4,order))))
    if m*m!=order: m=4;order=16
    levels=np.arange(-(m-1),m,2,dtype=float); norm=np.sqrt((2/3)*(order-1))
    blocks=[]
    for s in range(nsym):
        X=np.zeros(nfft*os,complex); half=occ//2
        bins=np.concatenate([np.arange(nfft*os-half,nfft*os),np.arange(1,half+1)])
        rng=np.random.default_rng(12345+s)
        X[bins]=(rng.choice(levels,len(bins))+1j*rng.choice(levels,len(bins)))/norm
        blocks.append(np.fft.ifft(X)*np.sqrt(len(X)))
    x=np.concatenate(blocks)[:n]
    x/=np.sqrt(max(np.mean(np.abs(x)**2),1e-30)); x*=10**(-obo_db/20)
    actual_papr=10*np.log10(np.max(np.abs(x)**2)/np.mean(np.abs(x)**2))
    cap=np.sqrt(np.mean(np.abs(x)**2)*10**(papr_db/10)); mag=np.abs(x)
    x=np.where(mag>cap,x/np.maximum(mag,1e-30)*cap,x)
    a=np.abs(x); pp=max(.5,rapp_p)
    ao=a/np.power(1+np.power(a,2*pp),1/(2*pp))
    y=np.where(a>0,x/np.maximum(a,1e-30)*ao,0j)
    g=np.vdot(x,y)/max(np.vdot(x,x).real,1e-30)
    e=y-g*x
    evm=100*np.sqrt(np.vdot(e,e).real/max(np.vdot(g*x,g*x).real,1e-30))
    N=1
    while N<len(y):N*=2
    P=np.abs(np.fft.fftshift(np.fft.fft(y,n=N)))**2;c=N//2;mh=max(2,int(N*(occ/(nfft*os))/2))
    main=P[c-mh:c+mh].sum();adj=max((P[c+mh:c+3*mh].sum()+P[c-3*mh:c-mh].sum())/2,1e-30)
    aclr=10*np.log10(max(main,1e-30)/adj)
    return {"evm_pct":float(evm),"aclr_proxy_db":float(aclr),"actual_papr_db":float(actual_papr)}
