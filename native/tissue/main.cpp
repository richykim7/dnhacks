// Conditional alanine exchange model using PhysiCell 1.14.2 and bundled BioFVM.
// Cell placement is fixed: mechanical migration and treatment delivery are out of scope.
#include "core/PhysiCell.h"
#include "modules/PhysiCell_standard_modules.h"
#include <fstream>
#include <iomanip>
#include <random>
#include <cmath>
#include <omp.h>
using namespace PhysiCell;
using namespace BioFVM;
int main(int argc,char** argv){
 if(argc!=16)return 2;
 const std::string out=argv[1];const int seed=std::stoi(argv[2]);
 const double duration=std::stod(argv[3]),dt=std::stod(argv[4]),dx=std::stod(argv[5]),D=std::stod(argv[6]),secretion=std::stod(argv[7]),uptake=std::stod(argv[8]),boundary=std::stod(argv[9]),threshold=std::stod(argv[10]),growth=std::stod(argv[11]);
 const double tumor_radius=std::stod(argv[12]),caf_shell=std::stod(argv[13]),caf_offset=std::stod(argv[15]);const int caf_count=std::stoi(argv[14]);
 omp_set_num_threads(1);SeedRandom(seed);std::mt19937 rng(seed);std::uniform_real_distribution<double> jitter(-1.5,1.5);
 microenvironment.set_density(0,"alanine","mM",D,0.0);
 microenvironment.resize_space(-160.,160.,-160.,160.,-160.,160.,dx,dx,dx);
 microenvironment.diffusion_decay_solver=diffusion_decay_solver__constant_coefficients_LOD_3D;
 std::vector<double> boundary_values{boundary};
 for(unsigned int i=0;i<microenvironment.mesh.voxels.size();i++){
  microenvironment.density_vector(i)[0]=boundary;
  auto p=microenvironment.mesh.voxels[i].center;
  if(std::abs(p[0])>160-dx||std::abs(p[1])>160-dx||std::abs(p[2])>160-dx)microenvironment.add_dirichlet_node(i,boundary_values);
 }
 microenvironment.set_substrate_dirichlet_activation(0,true);
 create_cell_container_for_microenvironment(microenvironment,30);
 initialize_default_cell_definition();cell_defaults.phenotype.secretion.sync_to_microenvironment(&microenvironment);
 std::vector<double> damage;std::vector<double> initial_volume;
 auto add=[&](double x,double y,double z,int type){auto c=create_cell();c->type=type;c->assign_position(x,y,z);c->set_total_volume(4.*3.141592653589793*9.*9.*9./3.);c->phenotype.geometry.radius=9.;
 c->phenotype.secretion.secretion_rates[0]=type==1?secretion:0.;c->phenotype.secretion.saturation_densities[0]=1.;c->phenotype.secretion.uptake_rates[0]=type==0?uptake:0.;
 c->phenotype.secretion.advance(c,c->phenotype,0.);c->set_internal_uptake_constants(dt);damage.push_back(0);initial_volume.push_back(c->phenotype.volume.total);};
 for(int z=-90;z<=90;z+=21)for(int y=-90;y<=90;y+=21)for(int x=-90;x<=90;x+=21)if(x*x+y*y+z*z<tumor_radius*tumor_radius)add(x+jitter(rng),y+jitter(rng),z+jitter(rng),0);
 for(int i=0;i<caf_count;i++){double z=1.-2.*(i+.5)/caf_count,r=sqrt(1-z*z),t=i*2.399963;add(caf_shell*r*cos(t)+caf_offset,caf_shell*z,caf_shell*r*sin(t),1);}
 std::ofstream meta(out+"/frames.csv");meta<<"frame,time,mass,minimum,maximum\n";int frame=0;double next=0;
 auto save=[&](double t){std::ofstream cs(out+"/cells-"+std::to_string(frame)+".csv");cs<<std::setprecision(12)<<"id,x,y,z,radius,type,dead,alanine,volume\n";for(auto c:*all_cells)cs<<c->ID<<","<<c->position[0]<<","<<c->position[1]<<","<<c->position[2]<<","<<c->phenotype.geometry.radius<<","<<c->type<<","<<c->phenotype.death.dead<<","<<microenvironment.nearest_density_vector(c->position)[0]<<","<<c->phenotype.volume.total<<"\n";
 std::ofstream fs(out+"/field-"+std::to_string(frame)+".f32",std::ios::binary);double mass=0,mn=1e100,mx=0;for(unsigned int i=0;i<microenvironment.mesh.voxels.size();i++){float v=microenvironment.density_vector(i)[0];fs.write(reinterpret_cast<char*>(&v),4);mass+=v*microenvironment.mesh.voxels[i].volume;mn=std::min(mn,double(v));mx=std::max(mx,double(v));}meta<<std::setprecision(12)<<frame<<","<<t<<","<<mass<<","<<mn<<","<<mx<<"\n";meta.flush();frame++;};
 for(unsigned int i=0;i<microenvironment.mesh.voxels.size();i++)microenvironment.density_vector(i)[0]=boundary;
 save(0);next=duration/4;
 const int steps=std::lround(duration/dt);
 for(int s=1;s<=steps;s++){
  microenvironment.simulate_cell_sources_and_sinks(dt);microenvironment.simulate_diffusion_decay(dt);
  for(size_t i=0;i<all_cells->size();i++){auto c=(*all_cells)[i];if(c->type||c->phenotype.death.dead)continue;double a=microenvironment.nearest_density_vector(c->position)[0];double support=(uptake/0.01)*a/(a+0.1);damage[i]=std::max(0.,damage[i]+dt*(threshold-support));
   if(damage[i]>120){c->phenotype.death.dead=true;c->phenotype.secretion.uptake_rates[0]=0;c->phenotype.secretion.advance(c,c->phenotype,0.);c->set_internal_uptake_constants(dt);}else{double v=c->phenotype.volume.total*exp(growth*dt*(support-threshold));c->set_total_volume(v);c->phenotype.geometry.radius=cbrt(3*v/(4*3.141592653589793));}
  }
  double t=s*dt;if(t>=next-1e-8||s==steps){save(t);next+=duration/4;}
 }
 return 0;
}
