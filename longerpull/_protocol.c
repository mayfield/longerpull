/*
 * Protocol handling for lp messages
 */

#include "Python.h"
#include <zlib.h>
#include <arpa/inet.h>



static unsigned char sof_magic = 194;

struct preamble {
    unsigned char sof;
    unsigned int size;
    unsigned int msg_id;
    unsigned char is_compressed;
} __attribute__ ((packed));



static inline unsigned char get_sof(int value) {
    return sof_magic ^ (value ^ 0xff);
}


static PyObject *encode_preamble(PyObject *self, PyObject *args) {
    struct preamble p;
    Py_buffer data;
    unsigned int size;
    unsigned int msg_id;

    if (!PyArg_ParseTuple(args, "Iy*p:encode_preamble", &msg_id, &data,
                          &p.is_compressed))
        return NULL;
    /* Add 1 to data.len to account for compression byte. */
    size = data.len + 1;
    PyBuffer_Release(&data);
    p.sof = get_sof(size + msg_id);
    p.size = htonl(size);
    p.msg_id = htonl(msg_id);
    return PyBytes_FromStringAndSize((char *) &p, sizeof(p));
}


static PyObject *decode_preamble(PyObject *self, PyObject *args) {
    struct preamble *p;
    Py_buffer data;
    unsigned int size;
    unsigned int msg_id;
    PyObject *psize = NULL;
    PyObject *pmsg_id = NULL;
    PyObject *pis_compressed = NULL;
    PyObject *ret = NULL;
    
    if (!PyArg_ParseTuple(args, "y*:decode_preamble", &data))
        return NULL;
    if ((unsigned) data.len < sizeof(struct preamble)) {
        PyBuffer_Release(&data);
        PyErr_SetString(PyExc_TypeError, "short buffer");
        return NULL;
    }
    p = (struct preamble *) data.buf;
    size = ntohl(p->size);
    msg_id = ntohl(p->msg_id);

    if (get_sof(size + msg_id) != p->sof) {
        PyErr_SetString(PyExc_TypeError, "start-of-frame error");
        return NULL;
    }

    /* This benches a little faster then Py_BuildValue */
    if ((psize = PyLong_FromUnsignedLong(size)) == NULL ||
        (pmsg_id = PyLong_FromUnsignedLong(msg_id)) == NULL ||
        (pis_compressed = PyBool_FromLong(p->is_compressed)) == NULL ||
        (ret = PyTuple_New(3)) == NULL)
        goto error;

    PyBuffer_Release(&data);
    PyTuple_SET_ITEM(ret, 0, psize);
    PyTuple_SET_ITEM(ret, 1, pmsg_id);
    PyTuple_SET_ITEM(ret, 2, pis_compressed);
    return ret;

  error:
    PyBuffer_Release(&data);
    Py_XDECREF(psize);
    Py_XDECREF(pmsg_id);
    Py_XDECREF(pis_compressed);
    return NULL;
}


static PyMethodDef _protocol_methods[] = {
    {"encode_preamble", encode_preamble, METH_VARARGS,
        "Encode a message preamble."},
    {"decode_preamble", decode_preamble, METH_VARARGS,
        "Decode the preamble of message."},
    {NULL, NULL, 0, NULL}
};


static struct PyModuleDef _protocol_module = {
    PyModuleDef_HEAD_INIT,
    "longerpull._protocol",
    "c speedups for protocol of longerpull",
    -1,
    _protocol_methods
};


PyMODINIT_FUNC PyInit__protocol(void) {
    return PyModule_Create(&_protocol_module);
}
