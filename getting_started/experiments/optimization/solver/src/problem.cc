#include "problem.hh"
#include "nlohmann/json.hpp"
#include <fstream>
#include <sstream>
using namespace nlohmann;

Problem::Problem(string path) {
  ifstream file(path);
  string str;
  if(file) {
    ostringstream ss;
    ss << file.rdbuf(); // reading data
    str = ss.str();
  }
  file.close();
  json j = json::parse(str);

  this->algorithm     = j["algorithm"];
  this->nb_iterations = j["nb_iterations"];

  this->N            = j["N"];
  this->NB_TYPES     = j["NB_TYPES"];
  this->average_load = j["average_load"];

  j["power_plant_types"].get_to(power_plant_types);
  j["avg_pmaxs"].get_to(avg_pmaxs);
  j["capacity_factor"].get_to(capacity_factor);
  j["target_energy_mix"].get_to(target_energy_mix);
}

vector<double> Problem::get_pmaxs(vector<int> x) {
  vector<double> pmaxs(this->NB_TYPES);
  for (int i = 0; i < this->N; i++) {
    int type = x[i];
    pmaxs[type] += this->avg_pmaxs[type];
  }
  return pmaxs;
}

vector<double> Problem::get_energy_mix(vector<double> pmaxs) {
  vector<double> apriori_energy_mix(this->NB_TYPES);
  double sum = 0;
  for (int i = 0; i < this->NB_TYPES; i++) {
    apriori_energy_mix[i] = this->capacity_factor[i] * pmaxs[i] / average_load;
    if (apriori_energy_mix[i] > 0)
      sum += apriori_energy_mix[i];
  }
  
  if (sum > 100) {
    apriori_energy_mix[0] -= (sum - 100);
    apriori_energy_mix[3] = 0;
  } 
  else if (pmaxs[3] > 0)
    apriori_energy_mix[3] = 100 - sum;
  else if (pmaxs[0] > 0)
    apriori_energy_mix[0] += 100 - sum;
  return apriori_energy_mix;
}

double Problem::objective(vector<int> x) {
  vector<double> pmaxs      = this->get_pmaxs(x);
  vector<double> energy_mix = this->get_energy_mix(pmaxs);

  double res = 0.0;
  for (int i = 0; i < this->NB_TYPES; i++) {
    res += pow(this->target_energy_mix[i] - energy_mix[i], 2);
  }
  return res;
}