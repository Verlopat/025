#include "dsu.hpp"
#include <cassert>
#include <iostream>
#include <thread>
#include <vector>
#include <algorithm>
int main() {
    for(const std::string variant : {"b1","b2","b3","b4","p1","a1","a2","a3"}) {
        constexpr uint32_t n=48; auto d=saw::make_dsu(n,variant); saw::Metrics m;
        for(uint32_t i=1;i<n;++i) assert(d->unite(i-1,i,m));
        for(uint32_t i=0;i<n;++i) assert(d->find(i,m)==d->find(0,m));
        assert(!d->unite(0,n-1,m)); assert(saw::invariant(*d));
        if(variant=="b1")continue;
        auto concurrent=saw::make_dsu(n,variant);
        std::vector<std::thread> ts;
        for(uint32_t tid=0;tid<4;++tid)ts.emplace_back([&,tid]{
            saw::Metrics local;
            for(uint32_t i=0;i<500;++i) {
                uint32_t a=(i*7+tid*13)%n,b=(i*11+tid)%n;
                concurrent->unite(a,b,local); concurrent->find(b,local);
            }
        });
        for(auto& t:ts)t.join();
        assert(saw::invariant(*concurrent));
        // Compare partition relation by building a sequential replay of all union pairs.
        saw::Sequential oracle(n); saw::Metrics om;
        for(uint32_t tid=0;tid<4;++tid)
            for(uint32_t i=0;i<500;++i)oracle.unite((i*7+tid*13)%n,(i*11+tid)%n,om);
        for(uint32_t a=0;a<n;++a)for(uint32_t b=0;b<n;++b)
            assert((concurrent->find(a,m)==concurrent->find(b,m))==
                   (oracle.find(a,om)==oracle.find(b,om)));
    }
    std::cout<<"All C++ tests passed\n";
}
