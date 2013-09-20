import locfns as lf
import numpy as np
from scipy import stats
import pandas as pd
from statsmodels.api import families
from statsmodels.formula.api import glm
import Rfunctions as rf
import warnings

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class EstimationError(Error):
    """Exception raised for errors in estimations.
	Attributes:
        expr---input expression in which the error occurred
        msg---explanation of the error"""
    def __init__(self, expr, msg):
        self.expr = expr
        self.msg = msg

def locfdr(zz, bre = 120, df = 7, pct = 0., pct0 = 1./4, nulltype = 1, type = 0, plot = 1, mult = None, mlests = None, main = ' ', sw = 0, verbose = True):
	"""ignore R match.call()"""
	zz = np.array(zz)
	mlest_lo = None
	mlest_hi = None
	yt = None
	x = None
	needsfix = 0
	try:
		brelength = len(bre)
		lo = min(bre)
		up = max(bre)
		bre = brelength
	except TypeError:
		try:
			len(pct)
			lo = pct[0]
			up = pct[1]
			# the following line is present to mimic how R handles [if (pct > 0)] (see code below) when pct is an array
			pct = pct[0]
		except TypeError:
			if pct == 0:
				lo = min(zz)
				up = max(zz)
			elif pct < 0:
				med = np.median(zz)
				lo = med + (1 - pct) * (min(zz) - med)
				up = med + (1 - pct) * (max(zz) - med)
			elif pct > 0:
				lo = np.percentile(zz, pct * 100)
				up = np.percentile(zz, (1 - pct) * 100)
	zzz = np.array([max(min(el, up), lo) for el in zz])
	breaks = np.linspace(lo, up, bre)
	x = (breaks[1:] + breaks[0:-1]) / 2.
	y = np.histogram(zzz, bins = len(breaks) - 1)[0]
	yall = y
	K = len(y)
	N = len(zz)
	if pct > 0:
		y[0] = min(y[0], 1.)
		y[K-1] = min(y[K-1], 1)
	if not type:
		basismatrix = rf.ns(x, df)
		X = np.ones((basismatrix.shape[0], basismatrix.shape[1]+1), dtype=np.float64)
		X[:, 1:] = basismatrix
		f = glm("y ~ basismatrix", data = dict(y=np.matrix(y).transpose(), basismatrix=basismatrix), family=families.Poisson()).fit().fittedvalues
	else:
		basismatrix = rf.poly(x, df)
		X = np.ones((basismatrix.shape[0], basismatrix.shape[1]+1), dtype=np.float64)
		X[:, 1:] = basismatrix
		f = glm("y ~ basismatrix", data = dict(y=np.matrix(y).transpose(), basismatrix=basismatrix), family=families.Poisson()).fit().fittedvalues
	fulldens = f
	l = np.log(f)
	Fl = f.cumsum()
	Fr = f[::-1].cumsum()
	D = ((y - f) / np.sqrt((f + 1)))
	D = sum(np.power(D[1:(K-1)], 2)) / (K - 2 - df)
	if D > 1.5:
		warnings.warn("f(z) misfit = " + str(round(D,1)) + ". Rerun with larger df.")
	if nulltype == 3:
		fp0 = pd.DataFrame(np.zeros((6,4)).fill(np.nan), index=['thest', 'theSD', 'mlest', 'mleSD', 'cmest', 'cmeSD'], columns=['delta', 'sigleft', 'p0', 'sigright'])
	else:
		fp0 = pd.DataFrame(np.zeros((6,3)).fill(np.nan), index=['thest', 'theSD', 'mlest', 'mleSD', 'cmest', 'cmeSD'], columns=['delta', 'sigma', 'p0'])
	fp0.loc['thest'][0:2] = np.array([0,1])
	fp0.loc['theSD'][0:2] = 0
	imax = np.where(max(l)==l)[0][0]
	xmax = x[imax]
	try:
		len(pct)
		pctlo = pct0[0]
		pctup = pct0[1]
	except TypeError:
		pctup = 1 - pct0
		pctlo = pct0
	lo0 = np.percentile(zz, pctlo*100)
	hi0 = np.percentile(zz, pctup*100)
	nx = len(x)
	i0 = np.array([i for i, el in enumerate(x) if el > lo0 and el < hi0])
	x0 = np.array([el for el in x if el > lo0 and el < hi0])
	y0 = np.array([el for i,el in enumerate(l) if x[i] > lo0 and x[i] < hi0])
	xsubtract = x0 - xmax
	X00 = np.zeros((2, len(xsubtract)))
	if nulltype == 3:
		X00[0, :] = np.power(xsubtract, 2)
		X00[1, :] = [max(el, 0)*max(el, 0) for el in xsubtract]
	else:
		X00[0, :] = xsubtract
		X00[1, :] = np.power(xsubtract, 2)
	X00 = X00.transpose()
	co = glm("y0 ~ X00", data = dict(y0=y0, X00=X00)).fit().params
	# these errors may not be necessary
	cmestloc = 'co = glm("y0 ~ X00", data = dict(y0=y0, X00=X00)).fit().params'
	if nulltype == 3 and ((pd.isnull(co[1]) or pd.isnull(co[2])) or (co[1] >= 0 or co[1] + co[2] >= 0)):
			raise EstimationError(cmestloc, 'CM estimation failed. Rerun with nulltype = 1 or 2.')
	elif pd.isnull(co[2]) or co[2] >= 0:
		if nulltype == 2:
			raise EstimationError(cmestloc, 'CM estimation failed. Rerun with nulltype = 1.')
		elif nulltype != 3:
			xsubtract2 = x - xmax
			X0 = np.ones((3, len(xsubtract2)))
			X0[1, :] = xsubtract2
			X0[2, :] = np.power(xsubtract2, 2)
			X0 = X0.transpose()
			warnings.warn('CM estimation failed; middle of histogram nonnormal')
	else:
		xsubtract2 = x - xmax
		X0 = np.ones((3, len(xsubtract2)))
		if nulltype == 3:
			X0[1, :] = np.power(xsubtract2, 2)
			X0[2, :] = [max(el, 0)*max(el, 0) for el in xsubtract2]
			sigs = np.array([1/np.sqrt(-2*co[1]), 1/np.sqrt(-2*(co[1]+co[2]))])
			fp0.loc['cmest', 0] = xmax
			fp0.loc['cmest', 1] = sigs[0]
			fp0.loc['cmest', 3] = sigs[1]
		else:
			X0[1, :] = xsubtract2
			X0[2, :] = np.power(xsuxfxbtract2, 2)
			xmaxx = -co[1] / (2 * co[2]) + xmax
			sighat = 1 / np.sqrt(-2 * co[2])
			fp0.loc('cmest', 0:2) = [xmaxx, sighat]
		X0 = X0.transpose()
		l0 = np.array((X0 * np.matrix(co).transpose()).transpose())[0]
		f0 = np.exp(l0)
		p0 = sum(f0) / float(sum(f))
		f0 = f0 / p0
		fp0.loc('cmest', 2) = p0
	b = 4.2 * np.exp(-0.26 * np.log10(N))
	if mlests == None:
		med = np.median(zz)
		sc = (np.percentile(zz, 75) - np.percentile(zz, 25)) / (2 * stats.norm.ppf(.75))
		mlests = locmle(zz, xlim = np.array([med, b * sc]))
		if N > 5e05:
			if verbose:
				warnings.warn("length(zz) > 500,000: an interval wider than the optimal one was used for maximum likelihood estimation. To use the optimal interval, rerun with mlests = [" + str(mlests[0]) + ", " + str(b * mlests[1]) + "].")
			mlest_lo = mlests[0]
			mlest_hi = b * mlests[1]
			needsfix = 1
			mlests = locmle(zz, xlim = [med, sc])
	if not pd.isnull(mlests):
		if N > 5e05:
			b = 1
		if nulltype == 1:
			Cov_in = {'x' : x, 'X' = X, 'f' = f, 'sw' = sw}
			ml_out = locmle(zz, xlim = [mlests[0], mlests[1]], d = mlests[0], s = mlests[1], Cov_in = Cov_in)
			mlests = ml_out['mle']
		else:
			mlests = locmle(zz, xlim = [mlests[0], b * mlests[1]], d = mlests[0], s = mlests[1])
		fp0.loc('mlest', 0:3) = mlests[0:3]
		fp0.loc('mleSD', 0:3) = mlests[3:6]
	if (not (pd.isnull(fp0.loc['mlest',0]) or pd.isnull(fp0.loc['mlest',1]) or pd.isnull(fp0.loc['cmest',0]) or pd.isnull(fp0.loc['cmest',1]))) and nulltype > 1:
		if abs(fp0.loc['cmest',0] - mlests[0]) > 0.05 or abs(np.log(fp0['cmest', 1] / mlests[1])) > 0.05:
			warnings.warn("Discrepancy between central matching and maximum likelihood estimates. Consider rerunning with nulltype = 1.")
	if pd.isnull(mlests[0]):
		if nulltype == 1:
			if pd.isnull(fp0.loc['cmest', 1]):
				raise EstimationError('pd.isnull(fp0.loc[\'cmest\', 1])', 'CM and ML estimation failed; middle of histogram is nonnormal.')
			else:
				raise EstimationError('pd.isnull(fp0.loc[\'cmest\', 1])', 'ML estimation failed. Rerun with nulltype = 2.')
		else:
			warnings.warn('ML estimation failed.')
	if nulltype < 2:
		xmaxx = mlests[0]
		xmax = mlests[0]
		delhat = mlests[0]
		sighat = mlests[1]
		p0 = mlests[2]
		f0 = np.array([stats.norm.pdf(el, delhat, sighat) for el in x])
		f0 = (sum(f) * f0) / sum(f0)
	fdr = np.array([min(el, 1) for el in (p0 * (f0 / f)])
	f00 = np.exp(-np.power(x, 2) / 2)
	f00 = (f00 * sum(f)) / sum(f00)
	p0theo = sum([f0[i] for i in i0]) / sum([f00[i] for i in i0])
	fp0.loc['thest', 2] = p0theo
	fdr0 = np.array([min(el, 1) for el in ((p0theo * f00) / f)])
	f0p = p0 * f0
	if nulltype == 0:
		f0p = p0theo * f00
	F0l = f0p.cumsum()
	F0r = f0p[::-1].cumsum()
	Fdrl = F0l / Fl
	Fdrr = (F0r / Fr)[::-1]
	Int = (1 - fdr) * f * (fdr < 0.9)
	if np.any([x[i] <= xmax and fdr[i] == 1 for i in xrange(len(fdr))]):
		xxlo = min([el for i,el in enumerate(x) if el <= xmax and fdr[i] == 1])
	else:
		xxlo = xmax
	if np.any([x[i] >= xmax and fdr[i] == 1 for i in xrange(len(fdr))]):
		xxhi = max([el for i,el in enumerate(x) if el >= xmax and fdr[i] == 1])
	else:
		xxhi = xmax
	indextest = [i for i,el in enumerate(x) if el >= xxlo and el <= xxhi]
	if len(indextest) > 0:
		for i in indextest:
			fdr[i] = 1
	indextest2 = [i for i,el in enumerate(x) if el <= xmax and fdr0[i] == 1]
	if len(indextest2) > 0:
		xxlo = min([x[i] for i in indextest2])
	else:
		xxlo = xmax
	indextest3 = [i for i,el in enumerate(x) if el >= xmax and fdr0[i] == 1]
	if len(indextest3) > 0:
		xxhi = max([x[i] for i in indextest3])
	else:
		xxhi = xmax
	if len(indextest) > 0:
		for i in indextest:
			fdr0[i] = 1
	if nulltype == 1:
		indextest4 = [i for i,el in enumerate(x) if el >= mlests[0] - mlests[1] and el <= mlests[0] + mlests[1]]
		for i in indextest4:
			fdr[i] = 1
			fdr0[i] = 1
	p1 = sum((1 - fdr) * f) / N
	p1theo = sum((1 - fdr0) * f) / N
	fall = f * (yall - y)
	Efdr = sum((1 - fdr) * fdr * fall) / sum((1 - fdr) * fall)
	Efdrtheo = sum((1 - fdr0) * fdr0 * fall) / sum((1 - fdr0) * fall)
	iup = [i for i,el in enumerate(x) if x >= xmax]
	ido = [i for i,el in enumerate(x) if x <= xmax]
	fdrido = np.array([fdr[i] for i in ido])
	fallido = np.array([fall[i] for i in ido])
	fdr0ido = np.array([fdr0[i] for i in ido])
	fdriup = np.array([fdr[i] for i in iup])
	falliup = np.array([fall[i] for i in iup])
	fdr0iup = np.array([fdr0[i] for i in iup])
	Eleft = sum((1 - fdrido) * fdrido * fallido) / sum((1 - fdrido) * fallido)
    Eleft0 = sum((1 - fdr0ido) * fdr0ido * fallido)/sum((1 - fdr0ido) * fallido)
    Eright = sum((1 - fdriup) * fdriup * falliup)/sum((1 - fdriup) * falliup)
    Eright0 = sum((1 - fdr0iup) * fdr0iup * falliup)/sum((1 - fdr0iup) * falliup)
    Efdr = np.array([Efdr, Eleft, Eright, Efdrtheo, Eleft0, Eright0])
    for i,el in enumerate(Efdr):
    	if pd.isnull(el):
    		Efdr[i] = 1
    Efdr = pd.Series(Efdr, index=['Efdr', 'Eleft', 'Eright', 'Efdrtheo', 'Eleft0', 'Eright0'])
    if nulltype == 0:
    	f1 = (1 - fdr0) * fall
    else:
    	f1 = (1 - fdr) * fall
    if mult != None:
    	try:
    		mul = np.ones(len(mult) + 1)
    		mul[1:] = mult
    	except TypeError:
    		mul = np.array([1, mult])
    	EE = np.zeros(len(mul))
    	for m in xrange(len(EE)):
    		xe = np.sqrt(mul[m]) * x
    		holder = {}
    		for i,el in enumerate(xe):
    			if not holder.has_key(el):
    				holder[el] = []
    			holder[el].append(f1[i])
    		together = []
    		for key in holder:
    			together.append([key, np.mean(holder[key])])
    		together.sort(key=lambda lam: lam[0])
    		together = np.array(together).transpose()
    		f1e = sp.interpolate.interp1d(together[0, :], together[1, :], bounds_error = False)(x)
    		for i,el in x:
    			if el > together[0, -1]:
    				f1e[i] = together[1, -1]
    			elif el < together[0, 0]:
    				f1e[i] = together[1, 0]
    		f1e = (f1e * sum(f1)) / sum(f1e)
    		f0e = f0
    		p0e = p0
    		if nulltype == 0:
    			f0e = f00
    			p0e = p0theo
    		fdre = (p0e * f0e) / (p0e * f0e + f1e)
    		Ee[m] = sum(f1e * fdre) / sum(f1e)
    	EE = EE / EE[0]
    	EE = pd.Series(EE, index=mult)
    Cov2_out = loccov2(X, X0, i0, f, fp0.loc('cmest'), N)
    Cov0_out = loccov2(x, )
