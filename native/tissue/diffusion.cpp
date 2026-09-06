// Independent closed-domain analytical/conservation checks for the pinned BioFVM solver.
#include "BioFVM/BioFVM.h"
#include <cmath>
#include <iostream>
#include <iomanip>
#include <omp.h>
using namespace BioFVM;
int main(int argc,char**argv){
 if(argc!=4)return 2;double dx=std::stod(argv[1]),dt=std::stod(argv[2]),tend=std::stod(argv[3]);
 omp_set_num_threads(1);Microenvironment m;m.set_density(0,"alanine","mM",300.,0.);
 m.resize_space(-160.,160.,-160.,160.,-160.,160.,dx,dx,dx);m.diffusion_decay_solver=diffusion_decay_solver__constant_coefficients_LOD_3D;
 const double pi=acos(-1.),L=320.;double initial_mass=0;
 for(unsigned int i=0;i<m.mesh.voxels.size();i++){auto p=m.mesh.voxels[i].center;double mode=1;for(double x:p)mode*=cos(pi*(x+160)/L);m.density_vector(i)[0]=.5+.2*mode;initial_mass+=m.density_vector(i)[0]*m.mesh.voxels[i].volume;}
 for(int s=0;s<std::lround(tend/dt);s++)m.simulate_diffusion_decay(dt);
 double mass=0,error=0,min=1,max=0;
 for(unsigned int i=0;i<m.mesh.voxels.size();i++){auto p=m.mesh.voxels[i].center;double mode=1;for(double x:p)mode*=cos(pi*(x+160)/L);double expected=.5+.2*mode*exp(-3*300*pi*pi*tend/(L*L)),v=m.density_vector(i)[0];error=std::max(error,std::abs(expected-v));mass+=v*m.mesh.voxels[i].volume;min=std::min(min,v);max=std::max(max,v);}
 std::cout<<std::setprecision(12)<<"{\"dx\":"<<dx<<",\"dt\":"<<dt<<",\"time\":"<<tend<<",\"max_absolute_error_mM\":"<<error<<",\"relative_mass_error\":"<<std::abs(mass-initial_mass)/initial_mass<<",\"minimum\":"<<min<<",\"maximum\":"<<max<<"}"<<std::endl;
}
