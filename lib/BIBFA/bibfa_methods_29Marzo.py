import numpy as np
from scipy import linalg
import copy
from scipy.stats import norm
from sklearn.preprocessing import label_binarize
import math
from sklearn.metrics import hamming_loss
#np.random.seed(0)

class BIBFA(object):    
    """ Bayessian Inter-Battery Factor Analysis
    BIBFA method for regression and classification, including multilabel and 
    categorical. It can function in both a supervised and semisupervised way. 
    At the same time, feature sparsity can be specified.
    
    This class estimates the parameters using the mean field approximation on 
    the graphical model.

    Parameters
    ----------
    __Kc : int, (default 2).
        number of components to extract.
    __prune : bool, (default 0).
        whether the pruning is used or not to remove the latent factors that 
        are not relevant.
    __hyper : list, (default None).
        hyperparameters used for the model.    
    __X_init : dict, (default None).
        Initialization of the variable X.
    __Z_init : dict, (default None).
        Initialization of the variable Z.
    __W_init : dict, (default [None]).
        Initialization of the variable W.
    __alpha_init : dict, (default None).
        Initialization of the variable alpha.
    __tau_init : dict, (default None).
        Initialization of the variable tau.
    __gamma_init : dict, (default None).
        Initialization of the variable gamma.
    
    Attributes
    ----------

    Example 1
    --------
    >>> import cca
    >>> model = cca.bibfa_methods.BIBFA(5, 0)
    >>> X0 = myModel_ml.struct_data(X, 0, 0)
    >>> X1 = myModel_ml.struct_data(Y, 0, 0)
    >>> myModel.fit(X0, X1, max_iter = 100)
    >>> prediction = myModel.predict([0], 1, 0, X0_2)
    
    """
    
    def __init__(self, Kc = 2, prune = 0,  hyper = None, X_init = None, 
                 Z_init = None, W_init = [None], alpha_init = None, 
                 tau_init = None, gamma_init = None):
        self.Kc = int(Kc) # Number of  latent variables
        self.prune = int(prune) # Indicates whether the pruning is to be done
        self.hyper = hyper 
        self.X_init = X_init
        self.Z_init = Z_init
        self.W_init = W_init
        self.alpha_init = alpha_init
        self.tau_init = tau_init
        self.gamma_init = gamma_init

    def fit(self, *args,**kwargs):
        """Fit model to data.
        
        Parameters
        ----------
        __X: dict, ('data', 'method', 'sparse').
            Dictionary with the information of the input views. Where 'data' 
            stores the matrix with the data. These matrices have size n_samples
            and can have different number of features. If one view has a number
            of samples smaller than the rest, these values are infered assuming
            it is a semisupervised scheme. This dictionary can be built using 
            the function "struct_data".
        __max_iter: int, (default 500),
            Maximum number of iterations done if not converged.
        __conv_crit: float, (default 1e-6).
            Convergence criteria for the lower bound.
        __verbose: bool, (default 0). 
            Whether or not to print all the lower bound updates.
        __Y_tst: dict, (default [None]).
            If specified, it is used as the output view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
        __X_tst: dict, (default [None]).
            If specified, it is used as the input view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
            
        """
        
        
        self.m = len(args)
        if self.hyper == None:
            self.hyper = HyperParameters(self.m)
        print ("\nFitting "+str(self.m)+" views")
        self.n = []
        self.d = []
        self.sparse = []
        self.method = []
        
        for (m,arg) in enumerate(args):
            self.sparse.append(arg['sparse'])
            self.method.append(arg['method'])
            if not (None in arg['data']):
                self.n.append(int(arg['data'].shape[0]))
                if arg['method'] == 0:   #Regression
                    self.d.append(int(arg['data'].shape[1]))
                elif arg['method'] == 1: #Categorical
                    self.d.append(int(len(np.unique(arg['data']))))
                elif arg['method'] == 2: #Categorical
                    self.d.append(int(arg['data'].shape[1]))
            elif not (None in self.W_init):
                self.n.append(0)
                self.d.append(self.W_init[m]['mean'].shape[0])      
        self.n_max = np.max(self.n)
        self.SS = self.n_max > self.n
        self.X = []
        self.t = []

        for (m,arg) in enumerate(args):
            mn = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])
            info = {
                "data":     np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m]),
                "mean":     mn,
                "cov":      mn**2 ,
                "prodT":    None,
                "LH":       None,
                "Elogp":    None,
            }
            self.X.append(info) 
            #Regression
            if arg['method'] == 0:   
                self.t.append(np.ones((self.n_max,)).astype(int)) 
                self.X[m]['data'] = arg['data']
                #SemiSupervised
                if self.SS[m]:   
                    #If the matrix is preinitialised
                    if (self.X_init is None):
                        self.X[m]['mean'][:self.n[m],:] = self.X[m]['data']  
                    else:                        
                        self.X[m]['mean'][:self.n[m],:] = self.X_init[m]['mean']
                    self.X[m]['cov'][:self.n[m],:] = self.X[m]['data']**2
                else:
                    self.X[m]['mean'] = self.X[m]['data']
                    self.X[m]['cov'] = self.X[m]['data']**2
            #Categorical
            elif arg['method'] == 1:
                self.t.append(np.ones((self.n_max,)).astype(int)) 
#                if self.SS[m]:
#                    self.t[m][:self.n[m]] = arg['data']                
#                else:
                self.t[m] = arg['data']                
                self.X[m]['mean'] = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])
                self.X[m]['cov'] = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])
            #Multilabel
            elif arg['method'] == 2: 
                self.t.append(copy.deepcopy(info))
                
                self.t[m]['data'] = arg['data']   
                #SemiSupervised
                if self.SS[m]:
                    self.t[m]['mean'] = (np.random.randint(2, size=[self.n_max, self.d[m]])).astype(float)
                    self.t[m]['mean'][:self.n[m],:] = (self.t[m]['data']).astype(float)
                    self.t[m]['cov'][:self.n[m],:] = (self.t[m]['data']**2).astype(float)
                    self.X[m]['mean'] = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])  
                    self.X[m]['cov'] = np.abs(np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m]))
                    #If the matrix is preinitialised
                    if not(self.X_init is None): 
                        #If only the supervised part of the matrix is preinitialised
                        if self.X_init[m]['mean'].shape[0]<self.n_max: 
                            self.X[m]['mean'][:self.n[m],:] = self.X_init[m]['mean']
                            self.X[m]['cov'][:self.n[m],:] = self.X_init[m]['cov']
                        #If all the matrix is preinitialised          
                        else: 
                            self.X[m]['mean'] = self.X_init[m]['mean']
                            self.X[m]['cov'] = self.X_init[m]['cov']
                else:
                    self.t[m]['mean'] = self.t[m]['data']
                    self.t[m]['cov'] = self.t[m]['data']**2 
                    if self.X_init is None:
                        self.X[m]['mean'] = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])  
                        self.X[m]['cov'] = np.abs(np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m]))
                    else:
                        if np.max(self.X_init[m]['mean']) == 1 and np.min(self.X_init[m]['mean']) == 0:
                            self.X[m]['mean'] = (2*self.X_init[m]['mean']-1).astype(float) #We cast the variables to a float in case the values used
                        else:
                            self.X[m]['mean'] = self.X_init[m]['mean'].astype(float) #We cast the variable to a float in case the values used
                        self.X[m]['cov'] = self.X_init[m]['cov'].astype(float) #We cast the variable to a float in case the values used
                          
        self.L = []
        self.mse = []
        self.HL = []

        if not (None in self.W_init):
            self.Kc = self.W_init[0]['mean'].shape[1]
            
        self.q_dist = Qdistribution(self.X, self.n, self.n_max, self.d, self.Kc, self.m, self.sparse, self.SS, self.hyper, 
                                    Z_init = self.Z_init, W_init = self.W_init, alpha_init = self.alpha_init, 
                                    tau_init = self.tau_init, gamma_init = self.gamma_init)               
#        self.q_dist = pickle.load( open( 'q_dist.pkl', "rb" ) )
#        with open('q_dist.pkl', 'wb') as output:
#            pickle.dump(self.q_dist, output, pickle.HIGHEST_PROTOCOL)
        self.fit_iterate(**kwargs)
    
    def fit_iterate(self, max_iter=500, pruning_crit = 1e-5, conv_crit=1e-6, verbose = 0, Y_tst=[None], X_tst=[None]):
        """Iterate to fit model to data.
        
        Parameters
        ----------
        __max_iter: int, (default 500),
            Maximum number of iterations done if not converged.
        __conv_crit: float, (default 1e-6).
            Convergence criteria for the lower bound.
        __verbose: bool, (default 0). 
            Whether or not to print all the lower bound updates.
        __Y_tst: dict, (default [None]).
            If specified, it is used as the output view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
        __X_tst: dict, (default [None]).
            If specified, it is used as the input view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
            
        """
        
        if verbose:
            self.L.append(self.update_bound())
            if not(None in Y_tst):
                if not(type(Y_tst) == dict):
                    Y_tst = self.struct_data(Y_tst, self.sparse[-1], self.method[-1])
                if not(None in X_tst):
                    if not(type(X_tst) == dict):
                        X_tst = self.struct_data(X_tst, self.sparse[-1], self.method[-1])
                self.HL.append(self.compute_HL(Y_tst, X_tst))
            print ('L(Q) inicial:%.1f' %  (self.update_bound()))
            print ('HL inicial:  %.4f' %  (self.compute_HL(Y_tst, X_tst)))  
            
        q = self.q_dist
        for i in range(max_iter):
            if verbose:
                print('Iteration %d' %(i+1))
            else:
                print('\rIteration %d Lower Bound %.1f K %d' %(i,self.update_bound(), q.Kc), end='\r', flush=True)
            
            # Update the variables of the model
            self.update(Y_tst, X_tst, verbose)
            
            # Pruning if specified after each iteration
            if self.prune:
                self.pruning(pruning_crit)
                if q.Kc == 0:
                    print('\nThere are no representative latent factors, no structure found in the data.')
                    return
            # Lower Bound convergence criteria
            if (len(self.L) > 2) and (abs(1 - self.L[-2]/self.L[-1]) < conv_crit):
                print('\nModel correctly trained. Convergence achieved')
                return
        print('')
#        print(self.update_bound())
#        q.Z['mean'] = np.hstack((q.Z['mean'],pruning_crit*np.ones((self.n_max,self.Kc))))
#        q.Z['cov'] = np.vstack((np.hstack((q.Z['cov'] - np.eye(q.Kc)*(1+pruning_crit),pruning_crit*np.ones((q.Kc,self.Kc-q.Kc)))),pruning_crit*np.ones((self.Kc-q.Kc,self.Kc)))) + np.eye(self.Kc)*(1-pruning_crit)
#        q.Z['prodT'] = np.vstack((np.hstack((q.Z['prodT'] - np.eye(q.Kc)*(1+pruning_crit),pruning_crit*np.ones((q.Kc,self.Kc-q.Kc)))),pruning_crit*np.ones((self.Kc-q.Kc,self.Kc)))) + np.eye(self.Kc)*(1-pruning_crit)
#         # Pruning W and alpha
#        for m in np.arange(self.m):
#            q.W[m]['mean'] = np.hstack((q.W[m]['mean'],pruning_crit*np.ones((self.d[m],self.Kc))))
#            q.W[m]['cov'] = np.vstack((np.hstack((q.W[m]['cov'] - np.eye(q.Kc)*(1+pruning_crit),pruning_crit*np.ones((q.Kc,self.Kc-q.Kc)))),pruning_crit*np.ones((self.Kc-q.Kc,self.Kc)))) + np.eye(self.Kc)*(1-pruning_crit)
#            q.W[m]['prodT'] = np.vstack((np.hstack((q.W[m]['prodT'] - np.eye(q.Kc)*(1+pruning_crit),pruning_crit*np.ones((q.Kc,self.Kc-q.Kc)))),pruning_crit*np.ones((self.Kc-q.Kc,self.Kc)))) + np.eye(self.Kc)*(1-pruning_crit)
#            q.alpha[m]['b'] = np.hstack((q.alpha[m]['b'], pruning_crit*np.ones((self.Kc - q.Kc,))))
#        q.Kc = self.Kc
#        self.L.append(self.update_bound())
#        print('Final L(Q):    %.1f' %  (self.update_bound()))
        
    def pruning(self, pruning_crit):
        """Pruning of the latent variables.
            
        Checks the values of the projection matrices W and keeps the latent 
        variables if there is no relevant value for any feature. Updates the 
        dimensions of all the model variables and the value of Kc.
        
        """
        
        q = self.q_dist
        fact_sel = np.array([])
        for m in np.arange(self.m):
            for K in np.arange(q.Kc):
                if any(abs(q.W[m]['mean'][:,K])>pruning_crit):
                    fact_sel = np.append(fact_sel,K)
        fact_sel = np.unique(fact_sel).astype(int)
        # Pruning Z
        q.Z['mean'] = q.Z['mean'][:,fact_sel]
        q.Z['cov'] = q.Z['cov'][fact_sel,:][:,fact_sel]
        q.Z['prodT'] = q.Z['prodT'][fact_sel,:][:,fact_sel]            
         # Pruning W and alpha
        for m in np.arange(self.m):
            q.W[m]['mean'] = q.W[m]['mean'][:,fact_sel]
            q.W[m]['cov'] = q.W[m]['cov'][fact_sel,:][:,fact_sel]
            q.W[m]['prodT'] = q.W[m]['prodT'][fact_sel,:][:,fact_sel]   
            q.alpha[m]['b'] = q.alpha[m]['b'][fact_sel]
        q.Kc = len(fact_sel)
        
    def struct_data(self, X, method, sparse = 0):
        """Fit model to data.
        
        Parameters
        ----------
        __X: dict, ('data', 'method', 'sparse').
            Dictionary with the information of the input views. Where 'data' 
            stores the matrix with the data. These matrices have size n_samples
            and can have different number of features. If one view has a number
            of samples smaller than the rest, these values are infered assuming
            it is a semisupervised scheme. This dictionary can be built using 
            the function "struct_data".
        __method: int.
            Indicates which type of vraible this is among these:
                0 - regression, floats (shape = [n_samples, n_features]).
                1 - categorical, integers (shape = [n_samples,])
                2 - multilabel, one-hot encoding (shape = [n_samples, n_targets])
            
        __sparse: bool, (default 0).
            Indicates if the variable wants to have sparsity in its features 
            or not.
            
        """
        X = {"data": X,
        "sparse": sparse,
        "method": method,
        }
        return X

    def compute_mse(self):
        q = self.q_dist
        mse = []
        for m in np.arange(self.m):
            if self.SS[m]:
                d = (self.X[m]['data'] - q.Z['mean'][:self.n[m],:].dot(q.W[m]['mean'].T)).ravel()        
            else:
                d = (self.X[m]['data'] - q.Z['mean'].dot(q.W[m]['mean'].T)).ravel()
            mse.append(d.dot(d) /self.n_max)

        return mse    
    
    def compute_HL(self, Y_tst, X_tst, m_in=[0], m_out=1, th=0):
        if None in X_tst:
            X_tst = self.X[m_in[0]]            
        if self.method[m_out] == 0:
            if self.SS[m_out]:
                Y_pred = (self.X[m_out]['mean'][self.n[m_out]:,:] > th).astype(int)
                HL = hamming_loss((Y_tst['data'] > th).astype(int), Y_pred)
            else:
                Y_pred = (self.predict(m_in, m_out, 0, X_tst) > th).astype(int)
                HL = hamming_loss((Y_tst['data'] > th).astype(int), Y_pred)
        elif self.method[m_out] == 2:
            if self.SS[m_out]:
                Y_pred = (self.t[m_out]['mean'][self.n[m_out]:,:] > 0.5).astype(int)
                HL = hamming_loss(Y_tst['data'], Y_pred)
            else:
                Y_pred = (self.predict(m_in, m_out, 0, X_tst) > 0.5).astype(int)
                HL = hamming_loss(Y_tst['data'], Y_pred)                   
        return HL

    def update(self, Y_tst, X_tst, verbose):
        """Update the variables of the model.
        
        This function updates all the variables of the model and stores the 
        lower bound as well as the Hamming Loss or MSE if specified.
        
        Parameters
        ----------
        __verbose: bool, (default 0). 
            Whether or not to print all the lower bound updates.
        __Y_tst: dict, (default [None]).
            If specified, it is used as the output view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
        __X_tst: dict, (default [None]).
            If specified, it is used as the input view to calculate the 
            Hamming Loss. This dictionary can be built using the function 
            "struct_data".
            
        """
        
        verboseprint = print if verbose else lambda *a, **k: None
        q = self.q_dist   
        for m in np.arange(self.m):
            self.update_w(m)
            verboseprint('L(Q) W%i:     %.1f' %  (m+1, self.update_bound()))
            verboseprint('HL W%i:       %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
        self.update_Z()
        verboseprint('L(Q) Z:      %.1f' %  (self.update_bound()))
        verboseprint('HL Z:        %.4f' %  (self.compute_HL(Y_tst, X_tst)))
        
        for m in np.arange(self.m):
            self.update_alpha(m)
            verboseprint('L(Q) alpha%i: %.1f' %  (m+1, self.update_bound()))
            verboseprint('HL alpha%i:   %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
            if self.method[m] == 0:   #Regression
                self.update_tau(m)
                verboseprint('L(Q) tau%i:   %.1f' %  (m+1, self.update_bound()))
                verboseprint('HL tau%i:     %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
                if self.SS[m]:
                    # Updating the mean and variance of X2* for the SS case
                    self.update_xs(m)
                    self.X[m]['mean'][self.n[m]:,:] = q.XS[m]['mean'][self.n[m]:,:]
                    self.X[m]['cov'][self.n[m]:,:] = np.ones((self.n_max-self.n[m],1)).dot(np.diag(q.XS[m]['cov'])[np.newaxis,:]) + q.XS[m]['mean'][self.n[m]:,:]**2
                    verboseprint('L(Q) X%i*:    %.1f' %  (m+1,self.update_bound()))
                    verboseprint('HL X%i*:      %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
            elif self.method[m] == 1: #Categorical
                 self.update_xcat(m)
                 verboseprint('L(Q) X%i*:     %.1f' %  (m+1, self.update_bound()))
                 verboseprint('HL X%i*:       %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
            elif self.method[m] == 2: #MultiLabel
#                self.update_tau(m)
                for i in np.arange(2):
                    self.update_x(m)
                    self.update_xi(m)
                    verboseprint('L(Q) X%i*:    %.1f' %  (m+1, self.update_bound()))
                    if self.SS[m]:
                        # Updating the mean and variance of X2* for the SS case
                        self.update_ts(m)
                        self.t[m]['mean'][self.n[m]:,:] = q.tS[m]['mean'][self.n[m]:,:]
                        self.update_xi(m)  
                        verboseprint('L(Q) t%i*:    %.1f' %  (m+1, self.update_bound()))
                    verboseprint ('HL X%i*:      %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
            if self.sparse[m]:
                self.update_gamma(m)
                verboseprint('L(Q) gamma%i: %.1f' %  (m+1, self.update_bound()))
                verboseprint('HL gamma%i:   %.4f' %  (m+1, self.compute_HL(Y_tst, X_tst)))
    
        self.L.append(self.update_bound())
        if not(None in Y_tst):
            if not(type(Y_tst) == dict):
                Y_tst = self.struct_data(Y_tst, self.sparse[-1], self.method[-1])
            if not(None in X_tst):
                if not(type(X_tst) == dict):
                    X_tst = self.struct_data(X_tst, self.sparse[-1], self.method[-1])
            self.HL.append(self.compute_HL(Y_tst, X_tst))
            
    def myInverse(self,X):
        """Computation of the inverse of a matrix.
        
        This function calculates the inverse of a matrix in an efficient way 
        using the Cholesky decomposition.
        
        Parameters
        ----------
        __A: bool, (default 0). 
            Whether or not to print all the lower bound updates.
            
        """
        
        try:
            L = linalg.pinv(np.linalg.cholesky(X), rcond=1e-10) #np.linalg.cholesky(A)
            B = np.dot(L.T,L) #linalg.pinv(L)*linalg.pinv(L.T)
            return B
        except:
            return np.nan  
        
    def sigmoid(self,x):
        """Computation of the sigmoid function.
        
        Parameters
        ----------
        __x: bool, (default 0). 
            Whether or not to print all the lower bound updates.
            
        """
        
        return 1. / (1 + np.exp(-x))
  
    def lambda_func(self,x):
        """Computation of the lambda function.
        
        This function calculates the lambda function defined in the paper.
        
        Parameters
        ----------
        __x: bool, (default 0). 
            Whether or not to print all the lower bound updates.
            
        """
        return (self.sigmoid(x) - 0.5)/(2*x)
          
    def update_Z(self):
        """Updates the variables Z.
        
        This function uses the variables of the learnt model to update Z.

        """
        q = self.q_dist
        
        aux = np.eye(q.Kc)
        for m in np.arange(self.m):
            aux += q.tau_mean(m)*q.W[m]['prodT']
        Z_cov = self.myInverse(aux)
        if not np.any(np.isnan(Z_cov)):
            # cov
            q.Z['cov'] = Z_cov
            # mean
            mn = np.zeros((self.n_max,q.Kc))
            for m in np.arange(self.m):
                mn += np.dot(self.X[m]['mean'],q.W[m]['mean']) * q.tau_mean(m)
            q.Z['mean'] = np.dot(mn,q.Z['cov'])
            # E[Y*Y^T]
            q.Z['prodT'] = np.dot(q.Z['mean'].T, q.Z['mean']) + self.n_max*q.Z['cov'] 
        else:
            print ('Cov Z is not invertible, not updated')
    
    def update_w(self, m):
        """Updates the variable W.
        
        This function uses the variables of the learnt model to update W of 
        the specified view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        q = self.q_dist
        
        if self.sparse[m]:
            q.W[m]['prodT'] = np.zeros((q.Kc,q.Kc))
            q.W[m]['prodTalpha'] = np.zeros((q.d[m],))
            q.W[m]['prodTgamma'] = np.zeros((q.Kc,))
            q.W[m]['sumlogdet'] = 0
                      
            for d in range(self.d[m]):
                w_cov = self.myInverse(np.diag(q.alpha_mean(m))*q.gamma_mean(m)[d] + q.tau_mean(m) * q.Z['prodT'])
                q.W[m]['cov'] += w_cov
                q.W[m]['mean'][d,:] = np.linalg.multi_dot([self.X[m]['mean'][:,d].T, q.Z['mean'] ,w_cov])*q.tau_mean(m)
                wwT = np.dot(q.W[m]['mean'][d,np.newaxis].T, q.W[m]['mean'][d,np.newaxis]) + w_cov
                q.W[m]['prodT'] += wwT
                DwwT = np.diag(wwT)
                q.W[m]['prodTgamma'] += q.gamma_mean(m)[d]*DwwT 
                q.W[m]['prodTalpha'][d] = np.dot(q.alpha_mean(m),DwwT)
                q.W[m]['sumlogdet'] += np.linalg.slogdet(w_cov)[1]
        else:
            # cov
            # w_cov = self.myInverse(np.diag(q.alpha_mean(m)) + q.tau_mean(m) * q.Z['prodT'])
            # Efficient and robust way of computing:  solve(diag(alpha) + tau * ZZ^T)
            tmp = 1/np.sqrt(q.alpha_mean(m))
            aux = np.outer(tmp,tmp)*q.Z['prodT'] + np.eye(q.Kc)/q.tau_mean(m)
            cho = np.linalg.cholesky(aux)            
            w_cov = 1/q.tau_mean(m) * np.outer(tmp,tmp) * np.dot(linalg.pinv(cho.T),linalg.pinv(cho))
            
            if not np.any(np.isnan(w_cov)):
                q.W[m]['cov'] = w_cov
                # mean
                q.W[m]['mean'] = q.tau_mean(m) * np.linalg.multi_dot([self.X[m]['mean'].T,q.Z['mean'],q.W[m]['cov']])
                #E[W*W^T]
                q.W[m]['prodT'] = np.dot(q.W[m]['mean'].T, q.W[m]['mean'])+self.d[m]*q.W[m]['cov']
            else:
                print ('Cov W' + str(m) + ' is not invertible, not updated')
            
    def update_alpha(self,m):
        """Updates the variable alpha.
        
        This function uses the variables of the learnt model to update alpha of 
        the specified view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        q = self.q_dist
        q.alpha[m]['a'] = (self.hyper.alpha_a[m] + 0.5 * self.d[m])/(self.d[m])
        if self.sparse[m]:
            prod = q.W[m]['prodTgamma']
        else:
            prod = np.diag(q.W[m]['prodT'])
        q.alpha[m]['b'] = (self.hyper.alpha_b[m] + 0.5 * prod)/(self.d[m])
        
    def update_tau(self,m):
        """Updates the variable tau.
        
        This function uses the variables of the learnt model to update tau of 
        the specified view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        q = self.q_dist
        q.tau[m]['a'] = (self.hyper.tau_a[m] + 0.5 * self.d[m]*self.n_max)/(self.d[m]*self.n_max) 
        q.tau[m]['b'] = (self.hyper.tau_b[m] + 0.5 *(np.sum(self.X[m]['mean'].ravel()**2)+ np.trace(np.dot(q.W[m]['prodT'],q.Z['prodT'])) - 2 * np.trace(np.linalg.multi_dot([q.W[m]['mean'], q.Z['mean'].T,self.X[m]['mean']])) ))/(self.d[m]*self.n_max)   
    
    def update_gamma(self,m):
        """Updates the variable gamma.
        
        This function uses the variables of the learnt model to update gamma of 
        the specified view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        q = self.q_dist     
        q.gamma[m]['a'] = (self.hyper.gamma_a[m] + 0.5 * q.Kc)/q.Kc
        q.gamma[m]['b'] = (self.hyper.gamma_b[m] + 0.5 *q.W[m]['prodTalpha'])/q.Kc
                     
    def update_xs(self,m): #Semisupervised
        """Updates the variable X*.
        
        This function uses the variables of the learnt model to update X* of 
        the specified view in the case of semisupervised learning.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        
        q = self.q_dist
        # cov
        q.XS[m]['cov'] = q.tau_mean(m)**(-1)*np.eye(self.d[m])
        # mean
        q.XS[m]['mean'] = np.dot(q.Z['mean'],q.W[m]['mean'].T)    
    
    def update_ts(self,m): 
        """Updates the variable t*.
        
        This function uses the variables of the learnt model to update t* of 
        the specified view in the case of semisupervised learning.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        
        q = self.q_dist
        # cov
        q.tS[m]['cov'] = self.sigmoid(self.X[m]['mean'])/(1 + np.exp(self.X[m]['mean']))
        # mean
        q.tS[m]['mean'] = self.sigmoid(self.X[m]['mean'])
        
    def update_x(self,m): #Multilabel
        """Updates the variable X.
        
        This function uses the variables of the learnt model to update X of 
        the specified view in the case of a multilabel view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        
        q = self.q_dist
        for n in np.arange(self.n_max):
            # cov
            self.X[m]['cov'][n,:] = (q.tau_mean(m) + 2*self.lambda_func(q.xi[m][n,:]))**(-1) #We store only the diagonal of the covariance matrix
            # mean
            self.X[m]['mean'][n,:] = np.dot((self.t[m]['mean'][n,:] - 0.5 + q.tau_mean(m)*np.dot(q.Z['mean'][n,:],q.W[m]['mean'].T)),np.diag(self.X[m]['cov'][n,:]))
            
    def update_xi(self,m): #Multilabel    
        """Updates the variable xi.
        
        This function uses the variables of the learnt model to update xi of 
        the specified view in the case of a multilabel view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        
        q = self.q_dist
        q.xi[m] = np.sqrt(self.X[m]['cov'] + self.X[m]['mean']**2)
        
    def expectation_aprx(self, a, b, c = [None], iterations = 100, n = None):
        """Calculates the expectation aproximation.
                
        Parameters
        ----------
        __a:
            
        __b:
            
        __c: float, (default [None])
                       
        __iterations: int, (default 100).
            
        __n: int, (default None).
            

        """

        if n == None:
            n = self.n_max
        exp = 0
        for it in np.arange(iterations):
            u = np.random.normal(0.0, 1.0, n)
            prod = 1
            for j in np.arange(np.shape(b)[1]):
                prod = prod * norm.cdf(u + a - b[:,j],0.0,1.0)
            if not (None in c):
                exp += norm.pdf(u, c - a, 1)*prod
            else:
                exp += prod
        return exp/iterations
    
    def update_xcat(self,m): #Multiclass
        """Updates the variable X.
        
        This function uses the variables of the learnt model to update X of 
        the specified view in the case of a categorical view.
        
        Parameters
        ----------
        __m: int. 
            This value indicates which of the input views is updated.

        """
        
        q = self.q_dist
        m_worm = np.dot(q.Z['mean'],q.W[m]['mean'].T)

        #Obtain the class-wise m_worm
# =============================================================================
#        Si es semisupervisado hay que cambiar la t
# =============================================================================
        set_classes = np.unique(self.t[m]['data']).astype(int) 
        t_b = label_binarize(self.t[m]['data'], classes=set_classes).astype(bool)
        m_wormi = m_worm[t_b]
        m_wormj = m_worm[~t_b].reshape(self.n_max,self.d[m]-1)
        #Aproximation of the expectation
        xi = self.expectation_aprx(m_wormi, m_wormj)
        #Mean value for Xnj / j!=i
        expj = np.zeros((self.n_max,self.d[m]-1))
        for j in np.arange(self.d[m]-1):
            m_wormk = m_wormj[:,np.arange(self.d[m]-1)!=j] #it extracts the mean of the values there are neither i nor j
            expj[:,j] = self.expectation_aprx(m_wormi, m_wormk, c = m_wormj[:,j], fact=1)
        # mean
        self.X[m]['mean'][~t_b] = (m_wormj - (expj.T/xi).T).flatten()
        self.X[m]['mean'][t_b] = m_wormi + np.sum(m_wormj - self.X[m]['mean'][~t_b].reshape(self.n_max,self.d[m]-1),axis=1)
    
    def predict(self,m_in,m_out,aprx=0,*args):
        """Apply the model learned in the training process to new data.
        
        This function uses the variables of the specified views to predict
        the output view.
        
        Parameters
        ----------
        __X: dict, ('data', 'method', 'sparse').
            Dictionary with the information of the input views. Where 'data' 
            stores the matrix with the data. These matrices have size n_samples
            and can have different number of features. If one view has a number
            of samples smaller than the rest, these values are infered assuming
            it is a semisupervised scheme. This dictionary can be built using 
            the function "struct_data".
            
        __m_in: list. 
            This value indicates which of the views are used as input.        
        __m_out: list. 
            This value indicates which of the input views is used as output.
        __aprx: bool (default 0).
            Whether or not to use the expectation aproximation.

        """
# =============================================================================
#         Hay que modificarlo para que pueda predecir todo lo que quieras a la vez. 
#         Para ello hay que definir un m_vec = [0,1,0,0,1] indicando qué vistas
#         son para calcular la predicción y cuáles para ser predichas.
# =============================================================================

        q = self.q_dist
        
        n_pred = np.shape(args[0]['data'])[0]        
        aux = np.eye(q.Kc)
        for m in m_in:
            aux += q.tau_mean(m)*np.dot(q.W[m]['mean'].T,q.W[m]['mean'])#q.W[m]['prodT']
        Z_cov = self.myInverse(aux)
        
        if not np.any(np.isnan(Z_cov)):
            Z_mean = np.zeros((n_pred,q.Kc))
            for (m,arg) in enumerate(args):
                Z_mean += np.dot(arg['data'],q.W[m_in[m]]['mean']) * q.tau_mean(m_in[m])
            Z_mean = np.dot(Z_mean,Z_cov)
        else:
            print ('Cov Z is not invertible')
        p_t = np.zeros((n_pred,self.d[m_out]))
        
        #Regression
        if self.method[m_out] == 0:   
            if aprx:
                 iterations = 100
                 for it in np.arange(iterations):
                    Z = np.random.normal(Z_mean,np.repeat(np.diag(Z_cov).reshape(1,q.Kc),Z_mean.shape[0],axis=0))
                    p_t += np.dot(Z,q.W[m_out]['mean'].T)
                 p_t = p_t/iterations
            else:
                var_x = q.tau_mean(m_out)**(-1)*np.eye(self.d[m_out]) + np.linalg.multi_dot([q.W[m_out]['mean'], Z_cov, q.W[m_out]['mean'].T])  #Variance               
                p_t = np.dot(Z_mean,q.W[m_out]['mean'].T) #Expectation
        
        #Categorical
        elif self.method[m_out] == 1: 
             if aprx: 
                 iterations = 100
                 for it in np.arange(iterations):
                    Z = np.random.normal(Z_mean,np.repeat(np.diag(Z_cov).reshape(1,q.Kc),self.n_max,axis=0))
                    m_zw = np.dot(Z,q.W[m_out]['mean'].T)
                    for i in np.arange(self.d[m_out]-1):
                        m_zwi = m_zw[:,i] #it extracts the mean of the values there are neither i nor j
                        m_zwj = m_zw[:,np.arange(self.d[m_out])!=i] #it extracts the mean of the values there are i
                        p_t[:,i] += self.expectation_aprx(m_zwi, m_zwj, n=n_pred)
                 p_t = p_t/iterations
             else:
                 m_zw = np.dot(Z_mean,q.W[m_out]['mean'].T)
                 for i in np.arange(self.d[m_out]-1):
                    m_zwi = m_zw[:,i] #it extracts the mean of the values there are netiher i
                    m_zwj = m_zw[:,np.arange(self.d[m_out])!=i] #it extracts the mean of the values there are j
                    p_t[:,i] += self.expectation_aprx(m_zwi, m_zwj, n=n_pred)   
             p_t[:,-1] = 1-np.sum(p_t[:,:-1],axis=1)
        
        #Multilabel
        elif self.method[m_out] == 2: 
            if aprx:
                 iterations = 100
                 for it in np.arange(iterations):
                    Z = np.random.normal(Z_mean,np.repeat(np.diag(Z_cov).reshape(1,q.Kc),Z_mean.shape[0],axis=0))
                    m_zw = np.dot(Z,q.W[m_out]['mean'].T)
                    p_t += self.sigmoid(m_zw*(1+math.pi/8*q.tau_mean(m_out))**(-0.5))
                 p_t = p_t/iterations
            else:
                m_x = np.dot(Z_mean,q.W[m_out]['mean'].T)        
                var_x = q.tau_mean(m_out)**(-1)*np.eye(self.d[m_out]) + np.linalg.multi_dot([q.W[m_out]['mean'], Z_cov, q.W[m_out]['mean'].T])
                for d in np.arange(self.d[m_out]):
                    p_t[:,d] = self.sigmoid(m_x[:,d]*(1+math.pi/8*var_x[d,d])**(-0.5))
        return p_t
       
    def HGamma(self, a, b):
        """Compute the entropy of a Gamma distribution.

        Parameters
        ----------
        __a: float. 
            The parameter a of a Gamma distribution.
        __b: float. 
            The parameter b of a Gamma distribution.

        """
        
        #return gammaln(a)-(a-1)*digamma(a)-np.log(b)+a
        return -np.log(b)
    
    def HGauss(self, mn, cov):
        """Compute the entropy of a Gamma distribution.
        
        Uses slogdet function to avoid numeric problems.
        
        Parameters
        ----------
        __mean: float. 
            The parameter mean of a Gamma distribution.
        __covariance: float. 
            The parameter covariance of a Gamma distribution.

        """
        
        return 0.5*mn.shape[0]*np.linalg.slogdet(cov)[1]
    
    def update_bound(self):
        """Update the Lower Bound.
        
        Uses the learnt variables to calculate the lower bound.
        
        """
        
# =============================================================================
#         Actualizar para pruning
# =============================================================================
        
        q = self.q_dist
        
        HZ = self.HGauss(q.Z['mean'], q.Z['cov'])
        if HZ == np.inf:
            HZ = q.Z['LH']
        q.Z['LH'] = HZ
        for m in np.arange(self.m):
            if self.sparse[m]:
                q.W[m]['LH'] = 0.5*q.W[m]['sumlogdet']
                q.gamma[m]['LH'] = np.sum(self.HGamma(q.gamma[m]['a'], q.gamma[m]['b']))
            else: 
                HW = self.HGauss(q.W[m]['mean'], q.W[m]['cov'])
                if HW == np.inf:
                    HW = q.W[m]['LH']
                q.W[m]['LH'] = HW
#            digammaa_tau = digamma()
            q.alpha[m]['LH'] = np.sum(self.HGamma(q.alpha[m]['a'], q.alpha[m]['b']))
            q.tau[m]['LH'] = np.sum(self.HGamma(q.tau[m]['a'], q.tau[m]['b']))
            if self.SS[m]:
                HXS = self.HGauss(q.XS[m]['mean'], q.XS[m]['cov'])
                if HXS == np.inf:
                    HXS = q.Z['LH']
                q.XS[m]['LH'] = HXS
#                if self.method[m] == 2:
#                    HtS = self.HGauss(q.tS[m]['mean'], np.diag(np.sum(q.tS[m]['cov'],axis=0)))
#                    if HtS == np.inf:
#                        HtS = q.Z['LH']
#                    q.tS[m]['LH'] = HtS
        EntropyQ = q.Z['LH']
        for m in np.arange(self.m):
            if self.sparse[m]:
                EntropyQ += q.gamma[m]['LH']
            EntropyQ += q.W[m]['LH'] + q.alpha[m]['LH']  + q.tau[m]['LH']
            if self.SS[m]:
                EntropyQ += q.XS[m]['LH']
#                if self.method[m] == 2:
#                    EntropyQ += q.tS[m]['LH']
        q.Z['Elogp'] = -0.5* np.trace(q.Z['prodT'])
        for m in np.arange(self.m):   
            if self.method[m] == 2: #MultiLabel
                q.tau[m]['ElogpXtau'] = np.sum(np.log(self.sigmoid(q.xi[m])) - q.xi[m]*0.5)
            else:
                q.tau[m]['ElogpXtau'] = -(0.5*self.n_max * self.d[m] + self.hyper.tau_a[m] -1)* np.log(q.tau[m]['b'])
            if self.sparse[m]: #Even though it sais Walp, it also includes the term related to gamma
                q.alpha[m]['ElogpWalp'] = -(0.5* self.d[m] + self.hyper.alpha_a[m] -1)* np.sum(np.log(q.alpha[m]['b'])) -(0.5* q.Kc + self.hyper.gamma_a[m] -1)* np.sum(np.log(q.gamma[m]['b'])) #- self.hyper.gamma_b[m]*np.sum(q.gamma_mean(m))
            else:                    
                q.alpha[m]['ElogpWalp'] = -(0.5* self.d[m] + self.hyper.alpha_a[m] -1)* np.sum(np.log(q.alpha[m]['b']))
        ElogP = q.Z['Elogp']
        for m in np.arange(self.m):
            ElogP += q.tau[m]['ElogpXtau'] + q.alpha[m]['ElogpWalp']
        return ElogP - EntropyQ

class HyperParameters(object):
    """ Hyperparameter initialisation.
    
    Parameters
    ----------
    __m : int.
        number of views in the model.
    
    """
    def __init__(self, m):
        self.alpha_a = []
        self.alpha_b = []
        self.gamma_a = []
        self.gamma_b = []
        self.tau_a = []
        self.tau_b = []
        self.xi = []
        for m in np.arange(m): 
            self.alpha_a.append(1e-14)
            self.alpha_b.append(1e-14)
            
            self.tau_a.append(1e-14)
            self.tau_b.append(1e-14)
            
            self.gamma_a.append(1)
            self.gamma_b.append(1)
            
class Qdistribution(object):
    """ Hyperparameter initialisation.
    
    Parameters
    ----------
    __m : int.
        number of views in the model.
    
    """
    def __init__(self, X, n, n_max, d, Kc, m, sparse, SS, hyper, Z_init=None, 
                 W_init=None, alpha_init=None, tau_init=None, gamma_init=None):
#    def __init__(self, n, n_max, d, Kc, m, sparse, hyper):
        self.n = n
        self.n_max = n_max
        self.d = d
        self.Kc = Kc
        self.m = m
        self.sparse = sparse
        self.SS = SS
        self.X = X
        
        # Initialize some parameters that are constant
        alpha = self.qGamma(hyper.alpha_a,hyper.alpha_b,self.m,(self.Kc*np.ones((self.m,))).astype(int))
        self.alpha = alpha if alpha_init is None else alpha_init
        tau = self.qGamma(hyper.tau_a,hyper.tau_b,self.m,(np.ones((self.m,))).astype(int))
        self.tau = tau if tau_init is None else tau_init
        #We generate gamma for all views, although the ones we are going to use and update are the ones for which has been specified the sparsity
        gamma = self.qGamma(hyper.gamma_a,hyper.gamma_b,self.m,self.d)
        self.gamma = gamma if gamma_init is None else gamma_init
        
        self.xi = []
        for m in np.arange(self.m):            
            self.xi.append(np.sqrt(self.X[m]['cov'] + self.X[m]['mean']**2))
#            self.xi.append(np.sqrt(self.X[m]['cov'] + self.X[m]['mean']**2)-100)
            
        # The remaning parameters at random 
        self.init_rnd(Z_init, W_init)

    def init_rnd(self, Z_init=None, W_init=None):
        """ Hyperparameter initialisation.
    
        Parameters
        ----------
        __m : int.
            number of views in the model.
            
        """
        
        W = []
        self.XS = []
        for m in np.arange(self.m):
            info = {
                "mean":     None,
                "cov":      None,
                "prodT":    None,
                "LH":       None,
                "Elogp":    None,
            }
            W.append(info)
        self.XS = copy.deepcopy(W)
        self.tS = copy.deepcopy(W)
        Z = copy.deepcopy(W[0])
            
        # Initialization of the latent space matrix Z
        Z['mean'] = np.random.normal(0.0, 1.0, self.n_max * self.Kc).reshape(self.n_max, self.Kc)
        Z['cov'] = np.eye(self.Kc) #np.dot(self.Z['mean'].T,self.Z['mean']) 
        Z['prodT'] = Z['cov'] + self.n_max*Z['cov'] #np.dot(self.Z['mean'].T, self.Z['mean']) + self.n_max*self.Z['cov']
        if Z_init is None: #If the matrix is not initialised
            self.Z = Z
        elif Z_init['mean'].shape[0]<self.n_max: #If only the supervised part of the matrix is initialised
            self.Z = Z
            self.Z['mean'][:Z_init['mean'].shape[0],:] = Z_init['mean']
            self.Z['cov'] = Z_init['cov']
            self.Z['prodT'] = Z_init['prodT']
        else: #If all the matrix is initialised          
            self.Z = Z_init
        
        for m in np.arange(self.m):
            # Initialization of the unknown data
            if self.SS[m]:
                self.tS[m]['mean'] = np.random.randint(2, size=[self.n_max, self.d[m]])
                self.tS[m]['cov'] = np.eye(self.d[m]) 
                self.XS[m]['mean'] = np.random.normal(0.0, 1.0, self.n_max * self.d[m]).reshape(self.n_max, self.d[m])
                self.XS[m]['cov'] = np.eye(self.d[m]) 
            # Initialization of the matrix W for each view
            for k in np.arange(self.Kc):
               W[m]['mean'] = np.random.normal(np.zeros((self.d[m],self.Kc)), 1/np.repeat(self.alpha_mean(m).reshape(1,self.Kc),self.d[m],axis=0)) #np.random.normal(0.0, 1.0, self.d[m] * self.Kc).reshape(self.d[m], self.Kc)
            W[m]['cov'] = np.dot(W[m]['mean'].T,W[m]['mean']) #np.eye(self.Kc)
            W[m]['prodT'] = np.dot(W[m]['mean'].T, W[m]['mean'])+self.Kc*W[m]['cov']
            if self.sparse[m]:
                W[m]['prodTalpha'] = np.zeros((self.d[m],))
                W[m]['prodTgamma'] = np.zeros((self.Kc,))
                W[m]['sumlogdet'] = 0
        self.W = W if None in W_init else W_init
               
    def qGamma(self,a,b,m_i,r):
        """ Initialisation of variables with Gamma distribution..
    
        Parameters
        ----------
        __a : array (shape = [m_in, 1]).
            Initialistaion of the parameter a.        
        __b : array (shape = [m_in, 1]).
            Initialistaion of the parameter b.
        __m_i: int.
            Number of views. 
        __r: array (shape = [m_in, 1]).
            dimension of the parameter b for each view.
            
        """
        
        param = []
        for m in np.arange(m_i):   
            info = {                
                "a":         a[m],
                "b":         (b[m]*np.ones((r[m],1))).flatten(),
                "LH":         None,
                "ElogpWalp":  None,
            }
            param.append(info)
        return param
#    def qGauss:
    
    def alpha_mean(self,m):
        """ Mean of alpha.
        It returns the mean value of the variable alpha for the specified view.
    
        Parameters
        ----------
        __m : int.
            View that wants to be used.
            
        """
        
        return self.alpha[m]["a"] / self.alpha[m]["b"]
    
    def tau_mean(self,m):
        """ Mean of tau.
        It returns the mean value of the variable tau for the specified view.
    
        Parameters
        ----------
        __m : int.
            View that wants to be used.
            
        """
        
        return self.tau[m]["a"] / self.tau[m]["b"]

    def gamma_mean(self,m):
        """ Mean of gamma.
        It returns the mean value of the variable gamma for the specified view.
    
        Parameters
        ----------
        __m : int.
            View that wants to be used.
            
        """
        
        return self.gamma[m]["a"] / self.gamma[m]["b"]