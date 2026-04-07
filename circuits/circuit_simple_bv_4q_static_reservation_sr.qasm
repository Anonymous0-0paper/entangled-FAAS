OPENQASM 2.0;
include "qelib1.inc";
gate gate_EfficientSU2(param0,param1,param2,param3,param4,param5,param6,param7,param8,param9,param10,param11,param12,param13,param14,param15,param16,param17,param18,param19,param20,param21,param22,param23) q0,q1,q2,q3 { ry(0) q0; ry(0) q1; ry(0) q2; ry(0) q3; rz(0) q0; rz(0) q1; rz(0) q2; rz(0) q3; cx q0,q1; cx q1,q2; cx q2,q3; ry(0) q0; ry(0) q1; ry(0) q2; ry(0) q3; rz(0) q0; rz(0) q1; rz(0) q2; rz(0) q3; cx q0,q1; cx q1,q2; cx q2,q3; ry(0) q0; ry(0) q1; ry(0) q2; ry(0) q3; rz(0) q0; rz(0) q1; rz(0) q2; rz(0) q3; }
qreg q[4];
gate_EfficientSU2(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0) q[0],q[1],q[2],q[3];
