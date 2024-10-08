.. _appendix-ref:

Appendix
========

Hint to avoid network errors
----------------------------

This section provide several hints, if you need to use aqtinstall in an environment that is limited to access the internet,
or mirror server you redirected seems broken.
You can find a description of the library to access network worked under the hood at first.
We also provide solutions for several typical cases you may encounter.  

Network access library
----------------------

The aqtinstall use `Requests`_ library to access the Qt binary archive repository provided by The Qt Foundation.
The `Requests`_ is very famous and a popular library in python ecosystem, which has many tips and tutorials on the net.
The aqtinstall has a special handler for HTTP direct, HTTP response code 30x, because the aqtinstall provides
blacklisting of proxy urls.

Zero trust network
------------------

The `Zero trust network` is popular administration concept in a enterprise local network.
Enterprise administrator force employers to install network traffic redirector agent in PC and tablet.
All the traffic are forwarded to cloud service that decrypt SSL communication and checks all the
employers communications. Security vendor emphasis it as "SECURE" by zero trust for employers privacy.

To realize it, all the communication between your PC to internet is encrypted with self-signed SSL certification.
Administrator force installing the self-signed root certificate to your PC's Cert Manager.

Python standard package manager utility PIP, and aqtinstall depends on ``certifi`` library for verification of SSL/TLS
certifications, and no trust for the cert manager of Operating System.
It will cause certification validation error when installing python packages, downloading Qt packages from the internet.

The list of trusted CAs can also be specified through the ``REQUESTS_CA_BUNDLE`` environment variable. 
You can check Requests manual section `SSL cert verification`_ for details.

.. _`Requests`: https://requests.readthedocs.io/en/latest/
.. _`SSL cert verification`: https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification

Got broken mirror
-----------------

When you got connection error with specific mirror site, when administrator of the mirror failed to configure the site,
or the site policy limit the access in specific IP range, but you are not in it in any reason, but https://download.qt.io/
mother site redirect you there.

Please check :ref:`configuration-ref` section how to specify a blacklist of proxy site.
