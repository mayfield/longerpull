longerpull
========
A long "pull" RPC service for Cradlepoint devices.


History
--------
This is a partial implementation of the Cradlepoint stream protocol.  The name
is a tongue and cheek shout-out to @sfresk who wrote the original stream server
under the name "longpoll" (if memory serves).


Goals
--------
The primary mission of this lib is to improve the performance of the low level
protocol used in a Cradlepoint stream connection.  This is done by providing
a C implementation of the boring parts of the protocol and using a thin python
wrapper to interface said C library to asyncio protocol interfaces.


Missing
--------
 1. **Client support:** In theory this could be adopted for use on the client
    side but no efforts have been made to directly support this side of the
    connection.  There may also be compatibility issues with 32bit platforms as
    this is also untested.
 2. **Command Implementations:**  This is a middle layer lib, no real efforts
    have been made to replace the entire Cradlepoint NCM service.
 3. **Tests:** Written entirely in boxer shorts and a cowboy hat.
 4. **Cluster support / Network Bus:** This is an ad-hoc style library, no
    communication bus is in place for doing message passing in the service
    plane.
