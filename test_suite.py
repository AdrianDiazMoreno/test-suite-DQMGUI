#!/usr/bin/env python

import glob
import time
import re
import random
import unittest, os
import urllib, json
import subprocess
import os, sys, urllib2, httplib, json
from array import *

ident = "DQMToJson/1.0 python/%d.%d.%d" % sys.version_info[:3]
HTTPS = httplib.HTTPSConnection

#######################################################
# Class Name: X509CertAuth
# Brief: Required class for the authentication process
#######################################################
class X509CertAuth(HTTPS):
  ssl_key_file = None
  ssl_cert_file = None

  def __init__(self, host, *args, **kwargs):
    HTTPS.__init__(self, host,
                  key_file = X509CertAuth.ssl_key_file,
                  cert_file = X509CertAuth.ssl_cert_file,
                  **kwargs)
#######################################################                                                                                       
# Class Name: X509CertOpen                                                                                                                    
# Brief: Mandatory class for the authentication process                                                                                       
#######################################################
class X509CertOpen(urllib2.AbstractHTTPHandler):
  def default_open(self, req):
    return self.do_open(X509CertAuth, req)

  def x509_params(self):
    key_file = cert_file = None

    x509_path = os.getenv("X509_USER_PROXY", None)
    if x509_path and os.path.exists(x509_path):
      key_file = cert_file = x509_path

    if not key_file:
      x509_path = os.getenv("X509_USER_KEY", None)
      if x509_path and os.path.exists(x509_path):
        key_file = x509_path

    if not cert_file:
      x509_path = os.getenv("X509_USER_CERT", None)
      if x509_path and os.path.exists(x509_path):
        cert_file = x509_path

    if not key_file:
      x509_path = os.getenv("HOME") + "/.globus/userkey.pem"
      if os.path.exists(x509_path):
        key_file = x509_path

    if not cert_file:
      x509_path = os.getenv("HOME") + "/.globus/usercert.pem"
      if os.path.exists(x509_path):
        cert_file = x509_path

    if not key_file or not os.path.exists(key_file):
      print >>sys.stderr, "no certificate private key file found"
      sys.exit(1)

    if not cert_file or not os.path.exists(cert_file):
      print >>sys.stderr, "no certificate public key file found"
      sys.exit(1)

    print "Using SSL private key", key_file
    print "Using SSL public key", cert_file
    return key_file, cert_file
 
  def dqm_get_histogram_json(self, server, run, dataset, folder):
    X509CertAuth.ssl_key_file, X509CertAuth.ssl_cert_file = self.x509_params()
    datareq = urllib2.Request('%s/jsonfairy/archive/%s/%s/%s'
             % (server, run, dataset, folder))
    datareq.add_header('User-agent', ident)
    return eval(urllib2.build_opener(X509CertOpen()).open(datareq).read(),
         { "__builtins__": None }, {})
 
  def dqm_get_json_re(self, server, dataset_re):
    X509CertAuth.ssl_key_file, X509CertAuth.ssl_cert_file = self.x509_params()
    datareq = urllib2.Request('%s/data/json/samples?match=%s'
             % (server, dataset_re))
    datareq.add_header('User-agent', ident)
    return eval(urllib2.build_opener(X509CertOpen()).open(datareq).read(),
         { "__builtins__": None }, {})


#######################################################                                                                                       
# Class name: TestDQMGUI                                                                                                                     
# Brief: Main test suite for DQMGUI                                                                                            
####################################################### 
class TestDQMGUI(unittest.TestCase):
  
  serverurl = 'https://cmsweb.cern.ch/dqm/dev'  
  dqmgui_path             = "/data/srv"
  test_upload_file_result = True
  file_new_name           = "ZeroBias19"
  run_number              = "277990"
  cert                    = X509CertOpen();

  
  #####################################################                                                                                       
  # Function description: The following function 
  # generates a random name for a dataset. This random
  # name is composed of two four letter words written 
  # in camelcase and followed by a number ranged from
  # 0 to 9 .
  #####################################################
  def _generate_random_dataset_name(self):
    name =''
    for i in range(1, 10):
      if i == 1 or i == 5: name = name + chr(random.randint(65,90))
      elif i == 9: name = name + str(random.randint(0, 9))
      else: name = name + chr(random.randint(97, 122))
    return name
      
  #####################################################
  # Test description: The following test checks that 
  # the indexing process is carried out as expected.
  #####################################################
  def test_A_upload_file(self):
    cwd = os.getcwd()
    #First it is required to change the current working directory
    #to the one that the DQMGUI uses
    os.chdir(self.dqmgui_path);
    for name in glob.glob('DQM_V0001_R000277990__*__Run2016F-PromptReco-v1__DQMIO.root'):
      #Generating random dataset name                                                                                                         
      dataset_new_name = self._generate_random_dataset_name()
      file_new_name = "DQM_V0001_R000277990__%s__Run2016F-PromptReco-v1__DQMIO.root" %dataset_new_name
      #Renaming file
      os.rename(name, file_new_name)
      #NOTE: This line could be hazardous according to Python official documentation since it is possible
      #to inject new code lines by shell.
      subprocess.call(['(source ./current/apps/dqmgui/128/etc/profile.d/env.sh &&                                                                                      visDQMUpload %s %s)' % (self.serverurl, file_new_name)], shell=True)
      #Now it is necessary to check if the file has been correctly indexed
      #Regular expression used for matching the dataset in which the file has been included
      dataset_re = '.*/%s/Run2016F-PromptReco-v1/DQMIO.*' % dataset_new_name
      #Obtaining JSON data (Timeout of 30 sec repeated 10 times)
      i        = 0
      uploaded = False
      while i <= 300 and not uploaded:
        data = self.cert.dqm_get_json_re(self.serverurl, dataset_re)
        #Extracting item (if exists)
        matchObj = re.match(".*(\{'importversion': \d+, 'run': '277990', 'version': '\d*', 'type': '.*', 'dataset': '/" + dataset_new_name + "/Run2016F-PromptReco-v1/DQMIO'\}).*",str(data))
        #If the element has been indexed correctly, then a match should be found
        uploaded = matchObj is not None and matchObj.group(1) is not None
        if not uploaded:
          print "Element not found or not indexed yet, waiting 30 seconds ..."
          time.sleep(30)
        #Continue
        i = i + 30
      if not uploaded:
        print "TIMEOUT! file %s could not been indexed correctly" % file_new_name
      self.test_upload_file_result = self.test_upload_file_result and uploaded
    #Checking the final result
    self.assertTrue(self.test_upload_file_result)
    os.chdir(cwd);
  #####################################################                                                                                       
  # Test description: This test checks that the
  # histograms of the file previously indexed are not
  # only available for download, but also available for
  # being used.
  #####################################################
  def test_B_histogram_1(self):
    # If the previous test has not been passed successfuly,
    # then this test cannot continue.
    self.assertTrue(self.test_upload_file_result)
    folder = 'Run2016F-PromptReco-v1/DQMIO/CSC/EventInfo/reportSummaryMap'
    # Obtaining histogram (NOTE: the organization of the downloaded histogram 
    # may be different from the one presented by using its raw url)
    data = self.cert.dqm_get_histogram_json(self.serverurl, self.run_number, self.file_new_name, folder)
    #Opening file
    f = open('./histograms/histogram_1.json', 'r')
    self.assertTrue(str(data) == f.read())

  #####################################################                                                                                       
  # Test description: This test checks that the                                                                                               
  # histograms of the file previously indexed are not                                                                                         
  # only available for download, but also available for                                                                                       
  # being used.                                                                                                                               
  #####################################################
  def test_B_histogram_2(self):
    # If the upload test  test has not been passed successfuly,
    # then this test cannot continue.                                                                                                         
    self.assertTrue(self.test_upload_file_result)
    folder = 'Run2016F-PromptReco-v1/DQMIO/EcalPreshower/EventInfo/reportSummaryMap'
    # Obtaining histogram (NOTE: the organization of the downloaded histogram                                                                 
    # may be different from the one presented by using its raw url)                                                                           
    data = self.cert.dqm_get_histogram_json(self.serverurl, self.run_number, self.file_new_name, folder)
    #Opening file                                                                                                                             
    f = open('./histograms/histogram_2.json', 'r')
    self.assertTrue(str(data) == f.read())

if __name__ == '__main__':
  unittest.main()
  
