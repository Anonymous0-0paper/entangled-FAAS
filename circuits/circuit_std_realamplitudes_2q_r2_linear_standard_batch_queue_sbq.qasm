OPENQASM 2.0;
include "qelib1.inc";
gate gate_RealAmplitudes(param0,param1,param2,param3,param4,param5) q0,q1 { ry(0) q0; ry(0) q1; cx q0,q1; ry(0) q0; ry(0) q1; cx q0,q1; ry(0) q0; ry(0) q1; }
qreg q[2];
gate_RealAmplitudes(0,0,0,0,0,0) q[0],q[1];
