#ifndef SCITBX_ARRAY_FAMILY_SELECTIONS_H
#define SCITBX_ARRAY_FAMILY_SELECTIONS_H

namespace scitbx { namespace af {

  template <typename IntType>
  af::shared<IntType>
  reindexing_array(
    std::size_t selectee_size,
    af::const_ref<IntType> const& iselection)
  {
    af::shared<IntType> result(selectee_size, selectee_size);
    IntType* result_begin = result.begin();
    for(std::size_t i=0;i<iselection.size();i++) {
      SCITBX_ASSERT(iselection[i] < selectee_size);
      result_begin[iselection[i]] = i;
    }
    return result;
  }

  template <typename MapType>
  af::shared<MapType>
  array_of_map_select(
    af::const_ref<MapType> const& self,
    af::const_ref<std::size_t> const& iselection)
  {
    std::size_t n = self.size();
    af::shared<std::size_t>
      reindexing_array = scitbx::af::reindexing_array(n, iselection);
    std::size_t* reindexing_array_begin = reindexing_array.begin();
    af::shared<MapType> result((af::reserve(iselection.size())));
    for(std::size_t i=0;i<iselection.size();i++) {
      result.push_back(MapType());
      MapType& new_map = result.back();
      MapType const& old_map = self[iselection[i]];
      for(typename MapType::const_iterator
            old_map_i=old_map.begin();
            old_map_i!=old_map.end();
            old_map_i++) {
        std::size_t j = reindexing_array_begin[old_map_i->first];
        if (j < n) {
          new_map[static_cast<typename MapType::key_type>(j)]
            = old_map_i->second;
        }
      }
    }
    return result;
  }

}} // namespace scitbx::af

#endif // SCITBX_ARRAY_FAMILY_SELECTIONS_H
