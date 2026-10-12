#include "dsu.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
#include <ctime>
#ifdef __linux__
#include <sys/resource.h>
#endif
using Clock=std::chrono::steady_clock;
struct Args {
    uint32_t n=64,threads=2,ops=500,find_percent=40;
    uint64_t seed=42,deadline_ms=0;
    std::string variant="p1",workload="w1",history="",pause_hook="none";
    uint32_t pause_us=0,pause_percent=0;
};
uint64_t scramble(uint64_t z) {
    z+=0x9e3779b97f4a7c15ULL;
    z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
    z=(z^(z>>27))*0x94d049bb133111ebULL;
    return z^(z>>31);
}
struct Op {bool is_find; uint32_t x,y;};
Op request(const Args& a,uint32_t tid,uint32_t i) {
    uint64_t k=scramble(a.seed ^ (uint64_t(tid)<<32) ^ i),j=scramble(k);
    auto pct=std::clamp(a.find_percent,0u,100u);
    bool is_find=k%100<pct;
    uint32_t x=uint32_t(j%a.n), y=uint32_t(scramble(j)%a.n);
    if(a.workload=="w2"||a.workload=="w5") { x=0;y=uint32_t(1+scramble(k+9)%(a.n-1)); }
    if(a.workload=="w3") { x=uint32_t((a.n-2)-(i%(a.n-1)));y=x+1; }
    if(a.workload=="w4") { x=uint32_t(j%(a.n/2)); y=uint32_t(a.n/2+scramble(j)%(a.n-a.n/2)); }
    if(a.workload=="w7")is_find=(k%100<99);
    if(a.workload=="w8")is_find=(k%100<15);
    if(a.workload=="w6") { x=uint32_t(j%a.n); y=uint32_t(scramble(j)%a.n); }
    return {is_find,x,y};
}
std::string quote(const std::string& s) {
    std::string o="\"";
    for(char c:s){ if(c=='"'||c=='\\')o+='\\'; if(c=='\n')o+="\\n";else o+=c; }
    return o+'"';
}
struct Event {uint64_t start,end;uint32_t tid,idx,x,y;bool is_find;uint32_t result;};
struct Local {
    saw::Metrics metrics;
    uint64_t executed=0,finds=0,unions=0,successes=0;
    std::vector<double> latencies;
    std::vector<Event> events;
};
Args parse(int argc,char** argv) {
    Args a;
    for(int i=1;i<argc;++i){
        auto flag=std::string(argv[i]);
        if(flag=="--help") { std::cout<<"--n N --threads N --ops N --seed N --variant b1|b2|b3|b4|p1|a1|a2|a3 --workload w1..w8 --find-percent 0..100 --history PATH --pause-hook after_root|before_cas|after_failure --pause-us N --pause-percent N --deadline-ms N\n";std::exit(0); }
        if(i+1>=argc) throw std::invalid_argument("missing value for "+flag);
        auto v=std::string(argv[++i]);
        if(flag=="--n")a.n=std::stoul(v);
        else if(flag=="--threads")a.threads=std::stoul(v);
        else if(flag=="--ops")a.ops=std::stoul(v);
        else if(flag=="--seed")a.seed=std::stoull(v);
        else if(flag=="--variant")a.variant=v;
        else if(flag=="--workload")a.workload=v;
        else if(flag=="--find-percent")a.find_percent=std::stoul(v);
        else if(flag=="--history")a.history=v;
        else if(flag=="--pause-hook")a.pause_hook=v;
        else if(flag=="--pause-us")a.pause_us=std::stoul(v);
        else if(flag=="--pause-percent")a.pause_percent=std::stoul(v);
        else if(flag=="--deadline-ms")a.deadline_ms=std::stoull(v);
        else throw std::invalid_argument("unknown flag: "+flag);
    }
    if(a.n<2||a.threads<1||a.threads>64||a.ops==0||a.find_percent>100||a.pause_percent>100||a.ops>100000000)
        throw std::invalid_argument("unsupported parameter range");
    if(a.variant=="b1"&&a.threads!=1)throw std::invalid_argument("b1 is single-threaded");
    if(a.workload.size()!=2||a.workload[0]!='w'||a.workload[1]<'1'||a.workload[1]>'8')
        throw std::invalid_argument("unknown workload");
    if(a.history.size() && uint64_t(a.ops)*a.threads>10000)throw std::invalid_argument("history is bounded to 10000 ops");
    return a;
}
double percentile(std::vector<double>& a,double p) {
    if(a.empty())return 0;
    std::sort(a.begin(),a.end());
    double pos=(a.size()-1)*p;size_t j=size_t(pos);
    if(j+1==a.size())return a.back();
    return a[j]+(pos-j)*(a[j+1]-a[j]);
}
int main(int argc,char** argv)try {
    const Args a=parse(argc,argv);
    saw::PauseConfig pause{a.pause_hook,a.pause_us,a.pause_percent,a.seed};
    auto d=saw::make_dsu(a.n,a.variant,pause);
    saw::Sequential oracle(a.n); saw::Metrics init_metrics;
    // Controlled initial deep chain; not part of timing or per-operation metrics.
    if(a.workload=="w7") {
        for(uint32_t i=a.n-1;i>0;--i){d->unite(i,i-1,init_metrics);oracle.unite(i,i-1,init_metrics);}
    }
    std::vector<Local> workers(a.threads);
    std::atomic<uint32_t> ready{0};std::atomic<bool> go{false};
    std::atomic<uint64_t> clock{0};
    std::vector<std::thread> threads;
    auto worker=[&](uint32_t tid) {
        auto& l=workers[tid]; l.latencies.reserve(std::min(a.ops,20000u));
        if(!a.history.empty())l.events.reserve(a.ops);
        ready.fetch_add(1,std::memory_order_release);
        while(!go.load(std::memory_order_acquire))std::this_thread::yield();
        const auto deadline=Clock::now()+std::chrono::milliseconds(a.deadline_ms);
        for(uint32_t i=0;i<a.ops;++i) {
            if(a.deadline_ms && Clock::now()>=deadline)break;
            auto op=request(a,tid,i);
            uint64_t begin=a.history.empty()?0:clock.fetch_add(1,std::memory_order_seq_cst);
            auto t0=Clock::now();
            uint32_t ret=0;
            if(op.is_find){ret=d->find(op.x,l.metrics);++l.finds;}
            else {ret=d->unite(op.x,op.y,l.metrics)?1:0;++l.unions;l.successes+=ret;}
            auto t1=Clock::now();
            uint64_t end=a.history.empty()?0:clock.fetch_add(1,std::memory_order_seq_cst);
            if(!a.history.empty())l.events.push_back({begin,end,tid,i,op.x,op.y,op.is_find,ret});
            if(i%std::max(1u,a.ops/20000)==0)
                l.latencies.push_back(std::chrono::duration<double,std::micro>(t1-t0).count());
            ++l.executed;
        }
    };
    for(uint32_t tid=0;tid<a.threads;++tid)threads.emplace_back(worker,tid);
    while(ready.load(std::memory_order_acquire)!=a.threads)std::this_thread::yield();
    const auto c0=std::clock();
    auto t0=Clock::now();go.store(true,std::memory_order_release);
    for(auto& t:threads)t.join();
    auto seconds=std::chrono::duration<double>(Clock::now()-t0).count();
    const auto cpu_seconds=double(std::clock()-c0)/CLOCKS_PER_SEC;
    double rss_mib=0;
#ifdef __linux__
    struct rusage usage{};
    if(getrusage(RUSAGE_SELF,&usage)==0)rss_mib=double(usage.ru_maxrss)/1024.0;
#endif
    saw::Metrics total;uint64_t count=0,finds=0,unions=0,successes=0;
    std::vector<double> lat;
    for(auto& w:workers) {
        total.add(w.metrics);count+=w.executed;finds+=w.finds;unions+=w.unions;successes+=w.successes;
        lat.insert(lat.end(),w.latencies.begin(),w.latencies.end());
    }
    // The final partition depends only on the union requests actually performed.
    saw::Metrics om;
    for(uint32_t tid=0;tid<a.threads;++tid)
        for(uint32_t i=0;i<workers[tid].executed;++i){auto op=request(a,tid,i);if(!op.is_find)oracle.unite(op.x,op.y,om);}
    // This comparison checks component equality even if the implementations choose different root IDs.
    bool valid=saw::invariant(*d);
    std::vector<uint32_t> actual(a.n), expected(a.n);
    saw::Metrics check_metrics;
    for(uint32_t x=0;x<a.n;++x){actual[x]=d->find(x,check_metrics);expected[x]=oracle.find(x,om);}
    std::vector<int64_t> map_actual(a.n,-1),map_expected(a.n,-1);
    for(uint32_t x=0;x<a.n;++x){
        auto ar=actual[x],er=expected[x];
        if(map_actual[ar]!=-1&&map_actual[ar]!=er)valid=false;
        if(map_expected[er]!=-1&&map_expected[er]!=ar)valid=false;
        map_actual[ar]=er;map_expected[er]=ar;
    }
    if(!a.history.empty()) {
        std::ofstream f(a.history);
        if(!f)throw std::runtime_error("cannot open history file");
        for(auto& w:workers)for(const auto& e:w.events) {
            f<<"{\"start\":"<<e.start<<",\"end\":"<<e.end
             <<",\"tid\":"<<e.tid<<",\"idx\":"<<e.idx
             <<",\"op\":\""<<(e.is_find?"find":"unite")<<"\",\"x\":"<<e.x
             <<",\"y\":"<<e.y<<",\"result\":"<<e.result<<"}\n";
        }
    }
    auto med=percentile(lat,.5),p95=percentile(lat,.95),p99=percentile(lat,.99);
    std::cout<<std::setprecision(10)<<"{\"variant\":"<<quote(a.variant)
      <<",\"workload\":"<<quote(a.workload)<<",\"n\":"<<a.n<<",\"threads\":"<<a.threads
      <<",\"ops_per_thread\":"<<a.ops<<",\"seed\":"<<a.seed<<",\"find_percent\":"<<a.find_percent
      <<",\"pause_hook\":"<<quote(a.pause_hook)<<",\"pause_us\":"<<a.pause_us
      <<",\"pause_percent\":"<<a.pause_percent<<",\"seconds\":"<<seconds
      <<",\"throughput\":"<<(count/seconds)
      <<",\"cpu_percent\":"<<(100*cpu_seconds/seconds)
      <<",\"rss_mib\":"<<rss_mib<<",\"submitted\":"<<uint64_t(a.threads)*a.ops
      <<",\"completed\":"<<count<<",\"finds\":"<<finds<<",\"unions\":"<<unions
      <<",\"successful_unions\":"<<successes<<",\"loads\":"<<total.loads<<",\"cas\":"<<total.cas
      <<",\"retries\":"<<total.failed<<",\"splits\":"<<total.splits<<",\"hops\":"<<total.hops
      <<",\"median_us\":"<<med<<",\"p95_us\":"<<p95<<",\"p99_us\":"<<p99
      <<",\"valid_final\":"<<(valid?"true":"false")<<"}\n";
    return valid?0:2;
} catch(const std::exception& e){std::cerr<<"saw_bench: "<<e.what()<<"\n";return 1;}
