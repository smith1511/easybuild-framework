import re
import os
from easybuild.framework.application import Application
from easybuild.tools.filetools import run_cmd

class ATLAS(Application):
    """
    Support for building ATLAS
    - configure (and check if it failed due to CPU throttling being enabled)
    - avoid parallel build (doesn't make sense for ATLAS and doesn't work)
    - make (optionally with shared libs), and install
    """
    def __init__(self, *args, **kwargs):
        Application.__init__(self, *args, **kwargs)

        self.cfg.update({
                         'ignorethrottling':[False, "Ignore check done by ATLAS for CPU throttling (not recommended) (default: False)"],
                         'full_lapack': [False, "Build a full LAPACK library (requires netlib's LAPACK) (default: False)"],
                         'sharedlibs':[True, "Enable building of shared libs as well (default: True)"]
                         })

    def configure(self):

        # configure for 64-bit build
        self.updatecfg('configopts', "-b 64")

        if self.getcfg('ignorethrottling'):
            # ignore CPU throttling check
            # this is not recommended, it will disturb the measurements done by ATLAS
            # used for the EasyBuild demo, to avoid requiring root privileges
            self.updatecfg('configopts', '-Si cputhrchk 0')

        # if LAPACK is found, instruct ATLAS to provide a full LAPACK library
        # ATLAS only provides a few LAPACK routines natively
        if self.getcfg('full_lapack'):
            if os.getenv('SOFTROOTLAPACK'):
                self.updatecfg('configopts', ' --with-netlib-lapack=%s/lib/liblapack.a' % os.getenv('SOFTROOTLAPACK'))
            else:
                self.log.error("netlib's LAPACK library not available, required to build ATLAS with a full LAPACK library.")

        # enable building of shared libraries (requires -fPIC)
        if self.getcfg('sharedlibs') or self.tk.opts['pic']:
            self.log.debug("Enabling -fPIC because we're building shared ATLAS libs, or just because.")
            self.updatecfg('configopts','-Fa alg -fPIC')

        # ATLAS only wants to be configured/built in a separate dir'
        try:
            objdir="obj"
            os.makedirs(objdir)
            os.chdir(objdir)
        except OSError, err:
            self.log.error("Failed to create obj directory to build in: %s" % err)

        # specify compilers
        self.updatecfg('configopts','-C ic %(cc)s -C if %(f77)s' % {
                                                                      'cc':os.getenv('CC'),
                                                                      'f77':os.getenv('F77')
                                                                      })

        # call configure in parent dir
        cmd = "%s %s/configure --prefix=%s %s" % (self.getcfg('preconfigopts'), self.getcfg('startfrom'),
                                                 self.installdir, self.getcfg('configopts'))
        (out, ec) = run_cmd(cmd, log_all=False, log_ok=False, simple=False)

        if ec != 0:
            throttling_regexp = re.compile("cpu throttling [a-zA-Z]* enabled", re.IGNORECASE)
            if throttling_regexp.search(out):
                errormsg="Configure failed, because CPU throttling is enabled; ATLAS doesn't like that. \
You can either disable CPU throttling, or set 'ignorethrottling' to True in the ATLAS .eb spec file. \
Also see http://math-atlas.sourceforge.net/errata.html#cputhrottle ."
            else:
                errormsg="""configure output: %s
Configure failed, not sure why (see output above).""" % out
            self.log.error(errormsg)

    # parallel build of ATLAS doesn't make sense (and doesn't work),
    # because it collects timing etc., so let's disable it
    def setparallelism(self):
        self.log.info("Disabling parallel build, makes no sense for ATLAS.")
        Application.setparallelism(self, 1)

    def make(self):

        # default make is fine
        Application.make(self, verbose=True)

        # optionally also build shared libs
        if self.getcfg('sharedlibs'):
            try:
                os.chdir('lib')
            except OSError, err:
                self.log.error("Failed to change to 'lib' directory for building the shared libs." % err)
            
            self.log.debug("Building shared libraries")
            cmd = "make shared cshared ptshared cptshared"
            run_cmd(cmd, log_all=True, simple=True)

            try:
                os.chdir('..')
            except OSError, err:
                self.log.error("Failed to get back to previous dir after building shared libs: %s " % err)

    def test(self):

        # always run tests
        if self.getcfg('runtest'):
            self.log.warning("ATLAS testing is done using 'make check' and 'make ptcheck', so no need to set 'runtest' in the .eb spec file.")

        # sanity tests
        self.setcfg('runtest', 'check')
        Application.test(self)

        # checks of threaded code
        self.setcfg('runtest', 'ptcheck')
        Application.test(self)

        # performance summary
        self.setcfg('runtest', 'time')
        Application.test(self)

    # default make install is fine

    def sanitycheck(self):
        """
        Custom sanity check for ATLAS
        """
        if not self.getcfg('sanityCheckPaths'):

            libs = ["atlas", "cblas", "f77blas", "lapack", "ptcblas", "ptf77blas"]

            static_libs = ["lib/lib%s.a" % x for x in libs]

            if self.getcfg('sharedlibs'):
                shared_libs = ["lib/lib%s.so" % x for x in libs]
            else:
                shared_libs = []

            self.setcfg('sanityCheckPaths',{'files':["include/%s" % x for x in ["cblas.h", "clapack.h"]] +
                                                    static_libs + shared_libs,
                                            'dirs':["include/atlas"]
                                           })

            self.log.info("Customized sanity check paths: %s"%self.getcfg('sanityCheckPaths'))

        Application.sanitycheck(self)