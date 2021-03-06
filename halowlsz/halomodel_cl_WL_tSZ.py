import os
import sys
import time
from configparser import ConfigParser
import numpy as np
from scipy import integrate
from scipy import special
from scipy.interpolate import interp1d, InterpolatedUnivariateSpline
import pylab as pl
from numba import jit
import timeit
#import fastcorr
from halowlsz.CosmologyFunctions import CosmologyFunctions
from halowlsz.mass_function import halo_bias_st, halo_bias_tinker, bias_mass_func_st, bias_mass_func_tinker, bias_mass_func_bocquet
from halowlsz.convert_NFW_RadMass import MfracToMvir, MvirToMRfrac, MfracToMfrac, MvirTomMRfrac, MfracTomMFrac, dlnMdensitydlnMcritOR200, HuKravtsov
from halowlsz.pressure_profiles import battaglia_profile_2d
from halowlsz.lensing_efficiency import Wkcom

__author__ = ("Vinu Vikraman <vvinuv@gmail.com>")

@jit(nopython=True)
def Wk_just_calling_from_lensing_efficiencyc(zl, chil, zsarr, chisarr, Ns, constk):
    #zl = lens redshift
    #chil = comoving distant to lens
    #zsarr = redshift distribution of source
    #Ns = Normalized redshift distribution of sources 
    al = 1. / (1. + zl)
    Wk = constk * chil / al
    gw = 0.0
    for i, N in enumerate(Ns):
        if chisarr[i] < chil  or  chisarr[i] == 0:
            continue
        gw += ((chisarr[i] - chil) * N / chisarr[i])
    gw *= (zsarr[1] - zsarr[0])
    Wk = Wk * gw
    return Wk

@jit(nopython=True)
def integrate_kyhalo(ell, lnzarr, chiarr, dVdzdOm, marr, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, zsarr, chisarr, Ns, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, kRmax, kRspace, yRmax, yRspace, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3): 
    '''
    Eq. 3.1 Ma et al. 
    '''    
    cl1h = 0.0
    cl2h = 0.0
    jj = 0
    for i, lnzi in enumerate(lnzarr):
        zi = np.exp(lnzi) - 1.
        zp = 1. + zi
        kl_yl_multi = Wkcom(zi, chiarr[i], zsarr, chisarr, Ns, constk) * consty / chiarr[i] / chiarr[i] / rhobarr[i] 
        mint = 0.0
        mk2 = 0.0
        my2 = 0.0
        #for mi in marr:
        for j in range(mspace):
            mi = marr[jj]
            kint = 0.0
            yint = 0.0
            if input_mvir:
                Mvir, Rvir, M200, R200, rho_s, Rs = MvirToMRfrac(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)
            else:
                Mvir, Rvir, M200, R200, rho_s, Rs = MfracToMvir(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)
            #Eq. 3.2 Ma et al
            rp = np.linspace(0, kRmax*Rvir, kRspace)
            for tr in rp:
                if tr == 0:
                    continue 
                kint += (tr * tr * np.sin(ell * tr / chiarr[i]) / (ell * tr / chiarr[i]) * rho_s / (tr/Rs) / (1. + tr/Rs)**2.)
            kint *= (4. * np.pi * (rp[1] - rp[0]))
            #Eq. 3.3 Ma et al
            xmax = yRmax * Rvir / Rs #Ma et al paper says that Eq. 3.3 convergence by r=5 rvir.
            xp = np.linspace(0, xmax, yRspace)
            ells = chiarr[i] / zp / Rs
            for x in xp:
                if x == 0:
                    continue 
                yint += (x * x * np.sin(ell * x / ells) / (ell * x / ells) * battaglia_profile_2d(x, 0., Rs, M200, R200, zi, rho_crit_arr[i], omega_b0, omega_m0, cosmo_h, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3))
            yint *= (4 * np.pi * Rs * (xp[1] - xp[0]) / ells / ells)
            mint += (dlnm * mf[jj] * kint * yint)
            mk2 += (dlnm * bias[jj] * mf[jj] * kint)
            my2 += (dlnm * bias[jj] * mf[jj] * yint)
            jj += 1
        cl1h += (dVdzdOm[i] * kl_yl_multi * mint * zp)
        cl2h += (dVdzdOm[i] * pk[i] * Darr[i] * Darr[i] * kl_yl_multi * mk2 * my2 * zp)
    cl1h *= dlnz
    cl2h *= dlnz
    cl = cl1h + cl2h
    return cl1h, cl2h, cl
 

@jit(nopython=True)
def integrate_kkhalo(ell, lnzarr, chiarr, dVdzdOm, marr, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, zsarr, chisarr, Ns, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, kRmax, kRspace): 
    '''
    Eq. 3.1 Ma et al. 
    '''    
   
    cl1h = 0.0
    cl2h = 0.0
    jj = 0
    for i, lnzi in enumerate(lnzarr):
        zi = np.exp(lnzi) - 1.
        zp = 1. + zi
        kl_multi = Wkcom(zi, chiarr[i], zsarr, chisarr, Ns, constk) / chiarr[i] / chiarr[i] / rhobarr[i] 
        mint = 0.0
        mk2 = 0.0
        #for mi in marr:
        for j in range(mspace):
            mi = marr[jj]
            kint = 0.0
            if input_mvir:
                Mvir, Rvir, M200, R200, rho_s, Rs = MvirToMRfrac(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)
            else:
                Mvir, Rvir, M200, R200, rho_s, Rs = MfracToMvir(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)
            #Eq. 3.2 Ma et al
            #limit_kk_Rvir.py tests the limit of Rvir. 
            rp = np.linspace(0, kRmax * Rvir, kRspace)
            for tr in rp:
                if tr == 0:
                    continue 
                kint += (tr * tr * np.sin(ell * tr / chiarr[i]) / (ell * tr / chiarr[i]) * rho_s / (tr/Rs) / (1. + tr/Rs)**2.)
            kint *= (4. * np.pi * (rp[1] - rp[0]))
            mint += (dlnm * mf[jj] * kint * kint)
            mk2 += (dlnm * bias[jj] * mf[jj] * kint)
            jj += 1
        cl1h += (dVdzdOm[i] * kl_multi * kl_multi * mint * zp)
        cl2h += (dVdzdOm[i] * pk[i] * Darr[i] * Darr[i] * kl_multi * kl_multi * mk2 * mk2 * zp)
    cl1h *= dlnz
    cl2h *= dlnz
    cl = cl1h + cl2h
    return cl1h, cl2h, cl
 
@jit(nopython=True)
def integrate_yyhalo(ell, lnzarr, chiarr, dVdzdOm, marr, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, yRmax, yRspace, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3):
    '''
    Eq. 3.1 Ma et al. 
    '''

    cl1h = 0.0
    cl2h = 0.0
    jj = 0
    for i, lnzi in enumerate(lnzarr[:]):
        zi = np.exp(lnzi) - 1.
        zp = 1. + zi
        mint = 0.0
        my2 = 0.0
        #for j, mi in enumerate(marr[:]):
        for j in range(mspace):
            mi = marr[jj]
            if input_mvir:
                Mvir, Rvir, M200, R200, rho_s, Rs = MvirToMRfrac(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)   
            else:
                Mvir, Rvir, M200, R200, rho_s, Rs = MfracToMvir(mi, zi, BDarr[i], rho_crit_arr[i], cosmo_h, frac=200.0)
            xmax = yRmax * Rvir / Rs
            ells = chiarr[i] / zp / Rs
            xarr = np.linspace(1e-5, xmax, yRspace)

            yint = 0.
            for x in xarr:
                if x == 0:
                    continue
                yint += (x * x * np.sin(ell * x / ells) / (ell * x / ells) * battaglia_profile_2d(x, 0., Rs, M200, R200, zi, rho_crit_arr[i], omega_b0, omega_m0, cosmo_h, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3))
            yint *= (4 * np.pi * Rs * (xarr[1] - xarr[0]) / ells / ells)

            mint += (dlnm * mf[jj] * yint * yint)
            my2 += (dlnm * bias[jj] * mf[jj] * yint)
            jj += 1
        cl1h += (dVdzdOm[i] * consty * consty * mint * zp)
        cl2h += (dVdzdOm[i] * pk[i] * Darr[i] * Darr[i] * consty * consty * my2 * my2 * zp)
    cl1h *= dlnz
    cl2h *= dlnz
    cl = cl1h + cl2h
    return cl1h, cl2h, cl


def cl_WL_tSZ(config_file, cosmology, fwhm_k, fwhm_y, kk, yy, ky, zsfile, 
              P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3, 
              omega_m0, sigma_8, odir, ofile):
    '''
    Compute WL X tSZ halomodel for a given source redshift distribution 
    '''
    if ky:
        sigma_k = fwhm_k * np.pi / 2.355 / 60. /180. #angle in radian
        sigma_y = fwhm_y * np.pi / 2.355 / 60. /180. #angle in radian
        sigmasq = sigma_k * sigma_y
    elif kk:
        sigma_k = fwhm_k * np.pi / 2.355 / 60. /180. #angle in radian
        sigmasq = sigma_k * sigma_k
    elif yy:
        sigma_y = fwhm_y * np.pi / 2.355 / 60. /180. #angle in radian
        sigmasq = sigma_y * sigma_y
    else:
        raise ValueError('Either kk, yy or ky should be True')


    config = ConfigParser()
    config.read(config_file)

    if omega_m0 is None:
        omega_m0 = config.getfloat(cosmology, 'omega_m0')
    if sigma_8 is None:
        sigma_8 = config.getfloat(cosmology, 'sigma_8')

    omega_l0 = 1. - omega_m0
    omega_b0 = config.getfloat(cosmology, 'omega_b0')
    h = config.getfloat(cosmology, 'h')
    n_scalar = config.getfloat(cosmology, 'n_scalar')    
    cosmo_dict = {'omega_m0':omega_m0, 'omega_l0':omega_l0, 'omega_b0':omega_b0, 'h':h, 'sigma_8':sigma_8, 'n_scalar':n_scalar}

    cosmo0 = CosmologyFunctions(0, config_file, cosmo_dict)
    cosmo_h = cosmo0._h

    save_clfile = config.getboolean('halomodel', 'save_clfile')
    print_cl = config.getboolean('halomodel', 'print_cl')
    light_speed = config.getfloat('halomodel', 'light_speed') #km/s
    mpctocm = config.getfloat('halomodel', 'mpctocm')
    kB_kev_K = config.getfloat('halomodel', 'kB_kev_K')
    sigma_t_cm = config.getfloat('halomodel', 'sigma_t_cm') #cm^2
    rest_electron_kev = config.getfloat('halomodel', 'rest_electron_kev') #keV
    constk = 3. * omega_m0 * (cosmo_h * 100. / light_speed)**2. / 2. #Mpc^-2
    consty = mpctocm * sigma_t_cm / rest_electron_kev 

    zsarr, Ns = np.genfromtxt(zsfile, unpack=True)
    if np.isscalar(zsarr):
        zsarr = np.array([zsarr])
        Ns = np.array([Ns])
    else:
        zint = np.sum(Ns) * (zsarr[1] - zsarr[0])
        Ns /= zint
    
    if P01 is None:
        P01 = config.getfloat('halomodel', 'P01')
    if P02 is None:
        P02 = config.getfloat('halomodel', 'P02')
    if P03 is None:
        P03 = config.getfloat('halomodel', 'P03')
    if xc1 is None:
        xc1 = config.getfloat('halomodel', 'xc1')
    if xc2 is None:
        xc2 = config.getfloat('halomodel', 'xc2')
    if xc3 is None:
        xc3 = config.getfloat('halomodel', 'xc3')
    if beta1 is None:
        beta1 = config.getfloat('halomodel', 'beta1')
    if beta2 is None:
        beta2 = config.getfloat('halomodel', 'beta2')
    if beta3 is None:
        beta3 = config.getfloat('halomodel', 'beta3')

    kRmax = config.getfloat('halomodel', 'kRmax') 
    kRspace = config.getint('halomodel', 'kRspace')
    yRmax = config.getfloat('halomodel', 'yRmax')
    yRspace = config.getint('halomodel', 'yRspace')

    kmin = config.getfloat('halomodel', 'kmin') #1/Mpc
    kmax = config.getfloat('halomodel', 'kmax')
    kspace = config.getint('halomodel', 'kspace')

    ellmin = config.getint('halomodel', 'ellmin') 
    ellmax = config.getfloat('halomodel', 'ellmax')
    ellspace = config.getint('halomodel', 'ellspace')

    mmin = config.getfloat('halomodel', 'mmin') 
    mmax = config.getfloat('halomodel', 'mmax')
    mspace = config.getfloat('halomodel', 'mspace')

    zmin = config.getfloat('halomodel', 'zmin')
    zmax = config.getfloat('halomodel', 'zmax')
    zspace = config.getfloat('halomodel', 'zspace')

    dlnk = np.log(kmax/kmin) / kspace
    lnkarr = np.linspace(np.log(kmin), np.log(kmax), kspace)
    karr = np.exp(lnkarr).astype(np.float64)
    #No little h
    #Input Mpc/h to power spectra and get Mpc^3/h^3
    pk_arr = np.array([cosmo0.linear_power(k/cosmo0._h) for k in karr]).astype(np.float64) / cosmo0._h / cosmo0._h / cosmo0._h
    #np.savetxt('pk_vinu.dat', np.transpose((karr/cosmo0._h, pk_arr*cosmo0._h**3)))
    #sys.exit()

    #kc, pkc = np.genfromtxt('matterpower.dat', unpack=True)
    #pkspl = InterpolatedUnivariateSpline(kc, pkc, k=2) 
    #pkh_arr = pkspl(karr/cosmo0._h)
    #pk_arr = pkh_arr / cosmo0._h / cosmo0._h / cosmo0._h

    pkspl = InterpolatedUnivariateSpline(karr, pk_arr, k=2) 
    #pl.loglog(karr, pk_arr)
    #pl.show()

    dlnm = np.log(mmax/mmin) / mspace
    lnmarr = np.linspace(np.log(mmin), np.log(mmax), mspace)
    marr = np.exp(lnmarr).astype(np.float64)
    lnzarr = np.linspace(np.log(1.+zmin), np.log(1.+zmax), zspace)
    zarr = np.exp(lnzarr) - 1.0
    dlnz = np.log((1.+zmax)/(1.+zmin)) / zspace

    print('dlnk, dlnm dlnz', dlnk, dlnm, dlnz)
    if doPrintCl:
        print('dlnk, dlnm dlnz', dlnk, dlnm, dlnz)
    #No little h
    #Need to give mass * h and get the sigma without little h
    #The following lines are used only used for ST MF and ST bias
    sigma_m0 = np.array([cosmo0.sigma_m(m * cosmo0._h) for m in marr])
    rho_norm0 = cosmo0.rho_bar()
    lnMassSigmaSpl = InterpolatedUnivariateSpline(lnmarr, sigma_m0, k=3)

    hzarr, BDarr, rhobarr, chiarr, dVdzdOm, rho_crit_arr = [], [], [], [], [], []
    bias, bias_t, Darr = [], [], []
    marr2, mf, dlnmdlnm, Deltaarr = [], [], [], []

    if config.get('halomodel', 'MF') == 'Tinker' and config.get('halomodel', 'MassToIntegrate') == 'm200m':
        #Mass using critical density (ie. m200c)
        tm200c = np.logspace(np.log10(1e8), np.log10(1e17), 50)
        #m200m mass using mean mass density
        tmarr = np.exp(lnmarr).astype(np.float64)

    #tf = np.genfromtxt('../data/z_m_relation.dat')
    #tz = tf[:,0]
    #tmv = tf[:,1]
    #tm200c = tf[:,2]
    #tm200m = tf[:,3]
    for i, zi in enumerate(zarr):
        cosmo = CosmologyFunctions(zi, config_file, cosmo_dict)
        rcrit = cosmo.rho_crit() * cosmo._h * cosmo._h
        rbar = cosmo.rho_bar() * cosmo._h * cosmo._h
        bn = cosmo.BryanDelta()
        BDarr.append(bn) #OK
        rho_crit_arr.append(rcrit) #OK
        rhobarr.append(rbar)
        chiarr.append(cosmo.comoving_distance() / cosmo._h)
        hzarr.append(cosmo.E0(zi))
        DD = bn/cosmo.omega_m()
        DD200 = 200./cosmo.omega_m()
        #Number of Msun objects/Mpc^3 (i.e. unit is 1/Mpc^3)
        
        if config.get('halomodel', 'MF') == 'Tinker':
            if config.get('halomodel', 'MassToIntegrate') == 'virial':
                if DD > 200:
                    mFrac = marr * cosmo_h 
                    print(1)
                    mFrac = marr * h0 
                    #print bn, cosmo.omega_m(), bn/cosmo.omega_m()
                    mf.append(bias_mass_func_tinker(zi, config_file, cosmo_dict, mFrac.min(), mFrac.max(), mspace, bias=False, Delta=DD, marr=mFrac, reduced=False)[1])
                    marr2.append(marr)
                    dlnmdlnm.append(np.ones_like(marr))
                else:
                    mFrac = np.array([HuKravtsov(zi, mv, rcrit, bn, config.getfloat('halomodel', 'MassDef') * cosmo.omega_m(), cosmo_h, 1)[2] for mv in marr]) * cosmo_h 
                    mf.append(bias_mass_func_tinker(zi, config_file, cosmo_dict,  mFrac.min(), mFrac.max(), mspace, bias=False, Delta=config.getfloat('halomodel', 'MassDef'), marr=mFrac, reduced=False)[1])
                    marr2.append(marr)
                    dlnmdlnm.append([dlnMdensitydlnMcritOR200(config.getfloat('halomodel', 'MassDef') * cosmo.omega_m(), bn, mFm/cosmo_h, mv, zi, cosmo_h, 1) for mv,mFm in zip(marr, mFrac)]) #dlnmFrac/dlnMv. In the bias_mass_func_tinker() I have computed dn/dlnM where M is in the unit of Msol. I have therefore include h in that mass function. Therefore, I just need to multiply dlnmFrac/dlnMv only 
                    print(2)
                    mFrac = np.array([HuKravtsov(zi, mv, rcrit, bn, float(config['massfunc']['MassDef'])/cosmo.omega_m(), h0, 1)[2] for mv in marr]) * h0 
                    mf.append(bias_mass_func_tinker(zi, mFrac.min(), mFrac.max(), mspace, bias=False, Delta=float(config['massfunc']['MassDef']), marr=mFrac, reduced=False)[1])
                    marr2.append(marr)
                    dlnmdlnm.append([dlnMdensitydlnMcritOR200(float(config['massfunc']['MassDef']) / cosmo.omega_m(), bn, mFm/h0, mv, zi, h0, 1) for mv,mFm in zip(marr, mFrac)]) #dlnmFrac/dlnMv. In the bias_mass_func_tinker() I have computed dn/dlnM where M is in the unit of Msol. I have therefore include h in that mass function. Therefore, I just need to multiply dlnmFrac/dlnMv only 
                #print dlnmdlnm
                #print a
                input_mvir = 1
            elif config.get('halomodel', 'MassToIntegrate') == 'm200c':
                #XXX
                #m200m = np.array([HuKravtsov(zi, mv, rcrit, 200, 200*cosmo.omega_m(), cosmo_h, 0)[2] for mv in marr]) #* cosmo_h
                #print m200m
                #XXX
                if DD200 > 200:
                    mFrac = marr * cosmo_h 
                    #print 200, cosmo.omega_m(), 200/cosmo.omega_m()
                    mf.append(bias_mass_func_tinker(zi, config_file, cosmo_dict, mFrac.min(), mFrac.max(), mspace, bias=False, Delta=DD200, marr=mFrac, reduced=False)[1])
                    marr2.append(marr)
                    dlnmdlnm.append(np.ones_like(marr))
                else:
                    mFrac = np.array([HuKravtsov(zi, m2c, rcrit, 200, config.getfloat('halomodel', 'MassDef') * cosmo.omega_m(), cosmo_h, 0)[2] for m2c in marr]) * cosmo_h
                    mf.append(bias_mass_func_tinker(zi, config_file, cosmo_dict, mFrac.min(), mFrac.max(), mspace, bias=False, Delta=config.getfloat('halomodel', 'MassDef'), marr=mFrac)[1])
                    marr2.append(marr)
                    for m2,mFm in zip(marr, mFrac):
                        dlnmdlnm.append(dlnMdensitydlnMcritOR200(config.getfloat('halomodel', 'MassDef') * cosmo.omega_m(), 200., mFm/cosmo_h, m2, zi, cosmo_h, 0)) #dlnM200m/dlnMv. In the bias_mass_func_tinker() I have computed dn/dlnM where M is in the unit of Msol. I have therefore include h in that mass function. Therefore, I just need to multiply dlnM200m/dlnMv only
                    mFrac = np.array([HuKravtsov(zi, m2c, rcrit, 200, float(config['massfunc']['MassDef'])/cosmo.omega_m(), h0, 0)[2] for m2c in marr]) * h0
                    mf.append(bias_mass_func_tinker(zi, mFrac.min(), mFrac.max(), mspace, bias=False, Delta=float(config['massfunc']['MassDef']), marr=mFrac)[1])
                    marr2.append(marr)
                    for m2,mFm in zip(marr, mFrac):
                        dlnmdlnm.append(dlnMdensitydlnMcritOR200(float(config['massfunc']['MassDef']) / cosmo.omega_m(), 200., mFm/h0, m2, zi, h0, 0)) #dlnM200m/dlnMv. In the bias_mass_func_tinker() I have computed dn/dlnM where M is in the unit of Msol. I have therefore include h in that mass function. Therefore, I just need to multiply dlnM200m/dlnMv only
                input_mvir = 0
            elif config.get('halomodel', 'MassToIntegrate') == 'm200m':
                #raise ValueError('Use MassToIntegrate=virial/m200c. m200m is not working')
                #Temporary mass array of m200m from m200c
                tm200m = np.array([HuKravtsov(zi, tt, rcrit, 200, 200.*cosmo.omega_m(), cosmo._h, 0)[2] for tt in tm200c])
                #m200m vs m200c spline 
                tmspl = InterpolatedUnivariateSpline(tm200m, tm200c)
                #Now m200c from m200m, i.e. tmarr which is the integrating
                #variable
                m200c = tmspl(tmarr)
                #m200m Msol/h
                m200m = tmarr * cosmo_h 
                marr2.append(m200c)
                mf.append(bias_mass_func_tinker(zi, config_file, cosmo_dict, m200m.min(), m200m.max(), mspace, bias=False, Delta=200, marr=m200m)[1])
                input_mvir = 0
        elif config.get('halomodel', 'MF') == 'Bocquet':
            if config.get('halomodel', 'MassToIntegrate') == 'virial':
                m200 = np.array([HuKravtsov(zi, mv, rcrit, bn, 200, cosmo_h, 1)[2] for mv in marr])
                mf.append(bias_mass_func_bocquet(zi, config_file, cosmo_dict, m200.min(), m200.max(), mspace, bias=False, marr=m200)[1])
                marr2.append(marr)
                for mv,m2 in zip(marr, m200):
                    dlnmdlnm.append(dlnMdensitydlnMcritOR200(200., bn, m2, mv, zi, cosmo_h, 1))
                input_mvir = 1
            elif config.get('halomodel', 'MassToIntegrate') == 'm200':
                tmf = bias_mass_func_bocquet(zi, config_file, cosmo_dict, marr.min(), marr.max(), mspace, bias=False, marr=marr)[1]
                mf.append(tmf)
                dlnmdlnm.append(np.ones(len(tmf)))
                input_mvir = 0
        elif config.get('halomodel', 'MF') == 'ST':
            mf.append(bias_mass_func_st(zi, config_file, cosmo_dict, marr.min(), marr.max(), mspace, bias=False, marr=marr)[1])
            marr2.append(marr)
            dlnmdlnm.append(np.ones_like(marr))
            input_mvir = 1
            #raise ValueError('MF should be Tinker or Bocquet')
        #Bias is calculated by assuming that the mass is virial. I need to change that
        #print DD
        #for m in marr:
        #    print '%.2e T %.2f'%(m, halo_bias_tinker(DD, cosmo.delta_c() / cosmo._growth / lnMassSigmaSpl(np.log(m))))
        #    print '%.2e ST %.2f'%(m, halo_bias_st(cosmo.delta_c() * cosmo.delta_c() / cosmo._growth / cosmo._growth / lnMassSigmaSpl(np.log(m)) / lnMassSigmaSpl(np.log(m))))
        #sys.exit()
        if config.get('halomodel', 'MF') == 'Tinker':
            if DD >= 200:
                bias.append(np.array([halo_bias_tinker(DD, cosmo.delta_c() / cosmo._growth / lnMassSigmaSpl(np.log(m))) for m in marr]))
            else:
                bias.append(np.array([halo_bias_tinker(config.getfloat('halomodel', 'MassDef') * cosmo.omega_m(), cosmo.delta_c() / cosmo._growth / lnMassSigmaSpl(np.log(m))) for m in mFrac/cosmo_h]))
        elif config.get('halomodel', 'MF') == 'ST' or config.get('halomodel', 'MF') == 'Bocquet':
            bias.append(np.array([halo_bias_st(cosmo.delta_c() * cosmo.delta_c() / cosmo._growth / cosmo._growth / lnMassSigmaSpl(np.log(m)) / lnMassSigmaSpl(np.log(m))) for m in marr]))
        dVdzdOm.append(cosmo.E(zi) / cosmo._h) #Mpc/h, It should have (km/s/Mpc)^-1 but in the cosmology code the speed of light is removed  
        Darr.append(cosmo._growth)

        #pl.title('%.2f'%zi)
        #pl.scatter(np.array([halo_bias_st(cosmo.delta_c() * cosmo.delta_c() / cosmo._growth / cosmo._growth / lnMassSigmaSpl(np.log(m)) / lnMassSigmaSpl(np.log(m))) for m in marr]), np.array([halo_bias_tinker(200, cosmo.delta_c() / cosmo._growth / lnMassSigmaSpl(np.log(m))) for m in marr]))
        #pl.show()

    if config.get('halomodel', 'MF') =='Tinker' and config.get('halomodel', 'MassToIntegrate') == 'm200m':  
        mf = np.array(mf).flatten()
    else: 
        mf = np.array(mf).flatten()  * np.array(dlnmdlnm).flatten()
    hzarr = np.array(hzarr)
    BDarr = np.array(BDarr)
    rhobarr = np.array(rhobarr)
    chiarr = np.array(chiarr)
    dVdzdOm = np.array(dVdzdOm) * chiarr * chiarr
    rho_crit_arr = np.array(rho_crit_arr)
    marr2 = np.array(marr2).flatten()
    zchispl = InterpolatedUnivariateSpline(zarr, chiarr, k=2)
    chisarr = zchispl(zsarr)
    bias = np.array(bias).flatten()
    bias_t = np.array(bias_t).flatten()
    Darr = np.array(Darr)

    #ellarr = np.linspace(1, 10001, 10)
    ellarr = np.logspace(np.log10(ellmin), np.log10(ellmax), ellspace)
    cl_arr, cl1h_arr, cl2h_arr = [], [], []
    for ell in ellarr:
        pk = pkspl(ell/chiarr)
        if ky: 
            cl1h, cl2h, cl = integrate_kyhalo(ell, lnzarr, chiarr, dVdzdOm, marr2, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, zsarr, chisarr, Ns, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, kRmax, kRspace, yRmax, yRspace, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3)
        if kk:
            cl1h, cl2h, cl = integrate_kkhalo(ell, lnzarr, chiarr, dVdzdOm, marr2, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, zsarr, chisarr, Ns, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, kRmax, kRspace)
        if yy:
            cl1h, cl2h, cl = integrate_yyhalo(ell, lnzarr, chiarr, dVdzdOm, marr2, mf, BDarr, rhobarr, rho_crit_arr, bias, Darr, pk, dlnz, dlnm, omega_b0, omega_m0, cosmo_h, constk, consty, input_mvir, mspace, yRmax, yRspace, P01, P02, P03, xc1, xc2, xc3, beta1, beta2, beta3)
        cl_arr.append(cl)
        cl1h_arr.append(cl1h)
        cl2h_arr.append(cl2h)
        if print_cl:
            print('l %.2 Cl_1h %.2e Cl_2h %.2e Cl %.2e'%(ell, cl1h, cl2h, cl))
        if doPrintCl:
            print(ell, cl1h, cl2h, cl)

    convolve = np.exp(-1 * sigmasq * ellarr * ellarr)# i.e. the output is Cl by convolving by exp(-sigma^2 l^2)
    cl = np.array(cl_arr) * convolve
    cl1h = np.array(cl1h_arr) * convolve
    cl2h = np.array(cl2h_arr) * convolve
    
    if save_clfile:
        np.savetxt(os.path.join(odir, ofile), np.transpose((ellarr, cl1h, cl2h, cl)), fmt='%.2f %.3e %.3e %.3e', header='l Cl1h Cl2h Cl')

    return ellarr, cl1h, cl2h, cl


if __name__=='__main__':
    fwhm_k = 0.0
    fwhm_y = 0.0
    kk = 0
    yy = 1
    ky = 0
    zsfile = 'source_distribution_zs_1.txt'
    #zsfile = 'CFHTLens_zdist.dat'

    ellarr, cl1h, cl2h, cl = cl_WL_tSZ(fwhm_k, fwhm_y, kk, yy, ky, zsfile, odir='../data')
    Omega_m0 = 0.25
    sigma_8 = 0.8
    paramsfile = 'wlxtsz.ini'
    zsfile = 'source_distribution_new_z1p0.txt'
    #zsfile = 'CFHTLens_zdist.dat'

    ellarr, cl1h, cl2h, cl = cl_WL_tSZ(paramsfile, fwhm_k, fwhm_y, kk, yy, ky, zsfile, omega_m0=Omega_m0, sigma_8=sigma_8, P01=18.1, P02=0.154, P03=-0.758, xc1=0.497, xc2=-0.00865, xc3=0.731, beta1=4.35, beta2=0.0393, beta3=0.415, odir='../data', default_pp=False)

    if yy:
        bl, bcl = np.genfromtxt('../data/battaglia_analytical.csv', delimiter=',', unpack=True)
        pl.plot(bl, bcl, label='Battaglia')
        #Convert y to \delta_T using 150 GHz. (g(x) TCMB)^2 = 6.7354
        cl *= 6.7354
        cl1h *= 6.7354
        cl2h *= 6.7354
        pl.plot(ellarr, 1e12 * ellarr * (ellarr+1) * cl / 2. / np.pi, label='Cl')
        pl.plot(ellarr, 1e12 * ellarr * (ellarr+1) * cl1h / 2. / np.pi, label='Cl1h')
        pl.plot(ellarr, 1e12 * ellarr * (ellarr+1) * cl2h / 2. / np.pi, label='Cl2h')
        pl.xlabel(r'$\ell$')
        pl.ylabel(r'$C_\ell \ell (\ell + 1)/2/\pi \mu K^2$')
        pl.legend(loc=0)
    else:
        pl.plot(ellarr, ellarr * (ellarr+1) * cl / 2. / np.pi, label='Cl')
        pl.plot(ellarr, ellarr * (ellarr+1) * cl1h / 2. / np.pi, label='Cl1h')
        pl.plot(ellarr, ellarr * (ellarr+1) * cl2h / 2. / np.pi, label='Cl2h')
        pl.xlabel(r'$\ell$')
        pl.ylabel(r'$C_\ell \ell (\ell + 1)/2/\pi$')
        pl.legend(loc=0)

    pl.show()
