#ifndef CCTBX_XRAY_AGARWAL_1978_H
#define CCTBX_XRAY_AGARWAL_1978_H

#include <cctbx/xray/sampled_model_density.h>

namespace cctbx { namespace xray {

  namespace detail {

    template <typename FloatType,
              typename CaasfType>
    class d_caasf_fourier_transformed
    :
      public caasf_fourier_transformed<FloatType, CaasfType>
    {
      public:
        d_caasf_fourier_transformed() {}

        d_caasf_fourier_transformed(
          exponent_table<FloatType>& exp_table,
          CaasfType const& caasf,
          std::complex<FloatType> const& fp_fdp,
          FloatType const& occupancy,
          FloatType const& w,
          FloatType const& u_iso,
          FloatType const& u_extra)
        :
          caasf_fourier_transformed<FloatType, CaasfType>(
            exp_table, caasf, fp_fdp, w, u_iso, u_extra),
          occupancy_(occupancy)
        {
          using scitbx::constants::pi_sq;
          FloatType b_incl_extra = adptbx::u_as_b(u_iso + u_extra);
          std::size_t i = 0;
          for(;i<caasf.n_ab();i++) {
            b_[i] = caasf.b(i) + b_incl_extra;
          }
          b_[i] = b_incl_extra;
          FloatType d = b_incl_extra * b_incl_extra * b_incl_extra;
          eight_pi_pow_3_2_w_d_ = const_8_pi_pow_3_2 * w / std::sqrt(d);
        }

        d_caasf_fourier_transformed(
          exponent_table<FloatType>& exp_table,
          CaasfType const& caasf,
          std::complex<FloatType> const& fp_fdp,
          FloatType const& occupancy,
          FloatType const& w,
          scitbx::sym_mat3<FloatType> const& u_cart,
          FloatType const& u_extra)
        :
          caasf_fourier_transformed<FloatType, CaasfType>(
            exp_table, caasf, fp_fdp, w, u_cart, u_extra),
          occupancy_(occupancy)
        {
          std::size_t i = 0;
          for(;i<caasf.n_ab();i++) {
            scitbx::sym_mat3<FloatType>
              b_all = compose_anisotropic_b_all(caasf.b(i), u_extra, u_cart);
            detb_[i] = b_all.determinant();
            bcfmt_[i] = b_all.co_factor_matrix_transposed();
          }
          scitbx::sym_mat3<FloatType>
            b_all = compose_anisotropic_b_all(0, u_extra, u_cart);
          detb_[i] = b_all.determinant();
          bcfmt_[i] = b_all.co_factor_matrix_transposed();
          FloatType d = b_all.determinant();
          eight_pi_pow_3_2_w_d_ = const_8_pi_pow_3_2 * w / std::sqrt(d);
        }

        scitbx::vec3<FloatType>
        d_rho_real_d_site(scitbx::vec3<FloatType> const& d,
                          FloatType const& d_sq) const
        {
          scitbx::vec3<FloatType> drds(0,0,0);
          if (!this->anisotropic_flag_) {
            for (std::size_t i=0;i<this->n_rho_real_terms;i++) {
              drds += d*(this->bs_real_[i]*2*this->rho_real_term(d_sq, i));
            }
          }
          else {
            for (std::size_t i=0;i<this->n_rho_real_terms;i++) {
              drds += this->aniso_bs_real_[i]*d*(2*this->rho_real_term(d, i));
            }
          }
          return drds;
        }

        scitbx::vec3<FloatType>
        d_rho_imag_d_site(scitbx::vec3<FloatType> const& d,
                          FloatType const& d_sq) const
        {
          if (!this->anisotropic_flag_) {
            return d*(this->bs_imag_*2*this->rho_imag(d_sq));
          }
          return this->aniso_bs_imag_*d*(2*this->rho_imag(d));
        }

        FloatType
        d_rho_real_d_u_iso(FloatType const& d_sq) const
        {
          using scitbx::constants::pi_sq;
          FloatType drdb(0);
          for(std::size_t i=0;i<b_.size();i++) {
            drdb += (3*b_[i] - 8*pi_sq*d_sq) / (2*b_[i]*b_[i])
                    * this->rho_real_term(d_sq, i);
          }
          return adptbx::u_as_b(drdb);
        }

        FloatType
        d_rho_imag_d_u_iso(FloatType const& d_sq) const
        {
          using scitbx::constants::pi_sq;
          FloatType b = b_[this->n_rho_real_terms-1];
          return adptbx::u_as_b(
            (3*b - 8*pi_sq*d_sq) / (2*b*b) * this->rho_imag(d_sq));
        }

        /* Mathematica script used to determine analytical gradients:
             bcart={{b00+bx,b01,b02},{b01,b11+bx,b12},{b02,b12,b22+bx}}
             binv=Inverse[bcart]
             detb=Det[bcart]
             d={dx,dy,dz}
             r=ca/Sqrt[detb] Exp[cb d.binv.d]
             g={{D[r,b00], D[r,b01], D[r,b02]},
                {D[r,b01], D[r,b11], D[r,b12]},
                {D[r,b02], D[r,b12], D[r,b22]}}
             bcfmt=binv*detb
             bd=bcfmt.d
             cbd=cb/detb
             chk={{  cbd bd[[1]] bd[[1]] + bcfmt[[1,1]]/2,
                   2 cbd bd[[1]] bd[[2]] + bcfmt[[1,2]],
                   2 cbd bd[[1]] bd[[3]] + bcfmt[[1,3]]},
                  {2 cbd bd[[1]] bd[[2]] + bcfmt[[1,2]],
                     cbd bd[[2]] bd[[2]] + bcfmt[[2,2]]/2,
                   2 cbd bd[[2]] bd[[3]] + bcfmt[[2,3]]},
                  {2 cbd bd[[1]] bd[[3]] + bcfmt[[1,3]],
                   2 cbd bd[[2]] bd[[3]] + bcfmt[[2,3]],
                     cbd bd[[3]] bd[[3]] + bcfmt[[3,3]]/2}}/(-detb)
             FullSimplify[g-r*chk]
        */
        scitbx::sym_mat3<FloatType>
        d_rho_real_d_b_cart(scitbx::vec3<FloatType> const& d) const
        {
          scitbx::sym_mat3<FloatType> drdb(0,0,0,0,0,0);
          for (std::size_t i=0;i<this->n_rho_real_terms;i++) {
            FloatType r = this->rho_real_term(d, i);
            scitbx::vec3<FloatType> bd = bcfmt_[i] * d;
            FloatType cbd = const_minus_4_pi_sq / detb_[i];
            FloatType rd = r / detb_[i];
            for(std::size_t j=0;j<3;j++) {
              drdb[j] += rd * (cbd*bd[j]*bd[j] + bcfmt_[i][j]*.5);
            }
            cbd *= 2;
            drdb[3] += rd * (cbd*bd[0]*bd[1] + bcfmt_[i][3]);
            drdb[4] += rd * (cbd*bd[0]*bd[2] + bcfmt_[i][4]);
            drdb[5] += rd * (cbd*bd[1]*bd[2] + bcfmt_[i][5]);
          }
          return drdb;
        }

        scitbx::sym_mat3<FloatType>
        d_rho_imag_d_b_cart(scitbx::vec3<FloatType> const& d) const
        {
          scitbx::sym_mat3<FloatType> drdb;
          FloatType r = this->rho_imag(d);
          std::size_t i = this->n_rho_real_terms-1;
          scitbx::vec3<FloatType> bd = bcfmt_[i] * d;
          FloatType cbd = const_minus_4_pi_sq / detb_[i];
          FloatType rd = r / detb_[i];
          for(std::size_t j=0;j<3;j++) {
            drdb[j] = rd * (cbd*bd[j]*bd[j] + bcfmt_[i][j]*.5);
          }
          cbd *= 2;
          drdb[3] = rd * (cbd*bd[0]*bd[1] + bcfmt_[i][3]);
          drdb[4] = rd * (cbd*bd[0]*bd[2] + bcfmt_[i][4]);
          drdb[5] = rd * (cbd*bd[1]*bd[2] + bcfmt_[i][5]);
          return drdb;
        }

        template <typename DistanceType>
        FloatType
        d_rho_real_d_occupancy(DistanceType const& d_or_d_sq) const
        {
          return -this->rho_real(d_or_d_sq) / occupancy_;
        }

        template <typename DistanceType>
        FloatType
        d_rho_imag_d_occupancy(DistanceType const& d_or_d_sq) const
        {
          return -this->rho_imag(d_or_d_sq) / occupancy_;
        }

        template <typename DistanceType>
        FloatType
        d_rho_real_d_fp(DistanceType const& d_or_d_sq) const
        {
          return -eight_pi_pow_3_2_w_d_
                 * this->exp_term(d_or_d_sq, this->n_rho_real_terms-1);
        }

        template <typename DistanceType>
        FloatType
        d_rho_imag_d_fdp(DistanceType const& d_or_d_sq) const
        {
          return d_rho_real_d_fp(d_or_d_sq);
        }

      protected:
        FloatType occupancy_;
        af::tiny<FloatType, CaasfType::n_plus_1> b_;
        af::tiny<FloatType, CaasfType::n_plus_1> detb_;
        af::tiny<scitbx::sym_mat3<FloatType>, CaasfType::n_plus_1> bcfmt_;
        FloatType eight_pi_pow_3_2_w_d_;
    };

  } // namespace detail

  template <typename FloatType = double,
            typename XrayScattererType = scatterer<> >
  class agarwal_1978
  {
    public:
      typedef XrayScattererType xray_scatterer_type;
      typedef typename xray_scatterer_type::caasf_type::base_type caasf_type;

      typedef typename maptbx::c_grid_padded_p1<3> accessor_type;
      typedef typename accessor_type::index_type grid_point_type;
      typedef typename grid_point_type::value_type grid_point_element_type;

      agarwal_1978() {}

      agarwal_1978(
        uctbx::unit_cell const& unit_cell,
        af::const_ref<XrayScattererType> const& scatterers,
        af::const_ref<std::complex<FloatType>, accessor_type> const& ft_dt,
        bool lifchitz,
        grid_point_type const& fft_n_real,
        grid_point_type const& fft_m_real,
        FloatType const& u_extra=0.25,
        FloatType const& wing_cutoff=1.e-3,
        FloatType const& exp_table_one_over_step_size=-100,
        bool force_complex=false,
        bool electron_density_must_be_positive=true);

      uctbx::unit_cell const&
      unit_cell() { return unit_cell_; }

      FloatType
      u_extra() const { return u_extra_; }

      FloatType
      wing_cutoff() const { return wing_cutoff_; }

      FloatType
      exp_table_one_over_step_size() const
      {
        return exp_table_one_over_step_size_;
      }

      std::size_t
      n_scatterers_passed() const { return n_scatterers_passed_; }

      std::size_t
      n_contributing_scatterers() const { return n_contributing_scatterers_; }

      std::size_t
      n_anomalous_scatterers() const { return n_anomalous_scatterers_; }

      bool
      anomalous_flag() const { return anomalous_flag_; }

      std::size_t
      exp_table_size() const { return exp_table_size_; }

      grid_point_type const&
      max_shell_radii() const { return max_shell_radii_; }

      fractional<FloatType>
      max_shell_radii_frac() const
      {
        fractional<FloatType> r;
        for(std::size_t i=0;i<3;i++) {
          r[i] = FloatType(max_shell_radii_[i]) / map_accessor_.focus()[i];
        }
        return r;
      }

      af::shared<std::complex<FloatType> >
      grad() const { return grad_; }

      af::shared<std::complex<FloatType> >
      grad_x() const { return grad_x_; }

      af::shared<std::complex<FloatType> >
      grad_y() const { return grad_y_; }

      af::shared<std::complex<FloatType> >
      grad_z() const { return grad_z_; }

      af::shared<std::complex<FloatType> >
      grad_u_iso() const { return grad_u_iso_; }

      af::shared<FloatType>
      grad_u_00() const { return grad_u_00_; }

      af::shared<FloatType>
      grad_u_11() const { return grad_u_11_; }

      af::shared<FloatType>
      grad_u_22() const { return grad_u_22_; }

      af::shared<FloatType>
      grad_u_01() const { return grad_u_01_; }

      af::shared<FloatType>
      grad_u_02() const { return grad_u_02_; }

      af::shared<FloatType>
      grad_u_12() const { return grad_u_12_; }

      af::shared<std::complex<FloatType> >
      grad_occupancy() const { return grad_occupancy_; }

      af::shared<std::complex<FloatType> >
      grad_fp() const { return grad_fp_; }

      af::shared<std::complex<FloatType> >
      grad_fdp() const { return grad_fdp_; }

    private:
      uctbx::unit_cell unit_cell_;
      std::size_t n_scatterers_passed_;
      FloatType u_extra_;
      FloatType wing_cutoff_;
      FloatType exp_table_one_over_step_size_;
      std::size_t n_anomalous_scatterers_;
      bool anomalous_flag_;
      std::size_t n_contributing_scatterers_;
      accessor_type map_accessor_;
      std::size_t exp_table_size_;
      grid_point_type max_shell_radii_;
      af::shared<std::complex<FloatType> > grad_;
      af::shared<std::complex<FloatType> > grad_x_;
      af::shared<std::complex<FloatType> > grad_y_;
      af::shared<std::complex<FloatType> > grad_z_;
      af::shared<std::complex<FloatType> > grad_u_iso_;
      af::shared<FloatType> grad_u_00_;
      af::shared<FloatType> grad_u_11_;
      af::shared<FloatType> grad_u_22_;
      af::shared<FloatType> grad_u_01_;
      af::shared<FloatType> grad_u_02_;
      af::shared<FloatType> grad_u_12_;
      af::shared<std::complex<FloatType> > grad_occupancy_;
      af::shared<std::complex<FloatType> > grad_fp_;
      af::shared<std::complex<FloatType> > grad_fdp_;
  };

  template <typename FloatType,
            typename XrayScattererType>
  agarwal_1978<FloatType, XrayScattererType>
  ::agarwal_1978(
    uctbx::unit_cell const& unit_cell,
    af::const_ref<XrayScattererType> const& scatterers,
    af::const_ref<std::complex<FloatType>, accessor_type> const& ft_dt,
    bool lifchitz,
    grid_point_type const& fft_n_real,
    grid_point_type const& fft_m_real,
    FloatType const& u_extra,
    FloatType const& wing_cutoff,
    FloatType const& exp_table_one_over_step_size,
    bool force_complex,
    bool electron_density_must_be_positive)
  :
    unit_cell_(unit_cell),
    n_scatterers_passed_(scatterers.size()),
    u_extra_(u_extra),
    wing_cutoff_(wing_cutoff),
    exp_table_one_over_step_size_(exp_table_one_over_step_size),
    n_contributing_scatterers_(0),
    n_anomalous_scatterers_(0),
    anomalous_flag_(false),
    exp_table_size_(0),
    max_shell_radii_(0,0,0)
  {
    scitbx::mat3<FloatType> orth_mx = unit_cell_.orthogonalization_matrix();
    if (orth_mx[3] != 0 || orth_mx[6] != 0 || orth_mx[7] != 0) {
      throw error(
        "Fatal Programming Error:"
        " Real-space sampling of model electron density"
        " is optimized for orthogonalization matrix"
        " according to the PDB convention. The orthogonalization"
        " matrix passed is not compatible with this convention.");
    }
    const xray_scatterer_type* scatterer;
    for(scatterer=scatterers.begin();scatterer!=scatterers.end();scatterer++) {
      if (scatterer->weight() == 0) continue;
      n_contributing_scatterers_++;
      if (scatterer->fp_fdp.imag() != 0) {
        n_anomalous_scatterers_++;
      }
    }
    if (n_anomalous_scatterers_ == 0 && !force_complex) {
      map_accessor_ = accessor_type(fft_m_real, fft_n_real);
    }
    else {
      anomalous_flag_ = true;
      map_accessor_ = accessor_type(fft_n_real, fft_n_real);
    }
    grid_point_type const& grid_f = map_accessor_.focus();
    grid_point_type const& grid_a = map_accessor_.all();
    detail::exponent_table<FloatType> exp_table(exp_table_one_over_step_size);
    for(scatterer=scatterers.begin();scatterer!=scatterers.end();scatterer++)
    {
      if (scatterer->weight() == 0) continue;
      FloatType fdp = scatterer->fp_fdp.imag();
      fractional<FloatType> coor_frac = scatterer->site;
      FloatType u_iso;
      scitbx::sym_mat3<FloatType> u_cart;
      if (!scatterer->anisotropic_flag) {
        u_iso = scatterer->u_iso;
      }
      else {
        u_cart = adptbx::u_star_as_u_cart(unit_cell_, scatterer->u_star);
        scitbx::vec3<FloatType> ev = adptbx::eigenvalues(u_cart);
        CCTBX_ASSERT(adptbx::is_positive_definite(ev));
        u_iso = af::max(ev);
      }
      CCTBX_ASSERT(u_iso >= 0);
      detail::d_caasf_fourier_transformed<FloatType, caasf_type> caasf_ft(
        exp_table,
        scatterer->caasf, scatterer->fp_fdp, scatterer->occupancy,
        scatterer->weight(), u_iso, u_extra_);
      detail::calc_shell<FloatType, grid_point_type> shell(
        unit_cell_, wing_cutoff_, grid_f, caasf_ft);
      detail::array_update_max(max_shell_radii_, shell.radii);
      if (electron_density_must_be_positive) {
        if (   caasf_ft.rho_real_0() < 0
            || caasf_ft.rho_real(shell.max_d_sq) < 0) {

          throw error("Negative electron density at sampling point.");
        }
      }
      if (scatterer->anisotropic_flag) {
        caasf_ft = detail::d_caasf_fourier_transformed<FloatType,caasf_type>(
          exp_table,
          scatterer->caasf, scatterer->fp_fdp, scatterer->occupancy,
          scatterer->weight(), u_cart, u_extra_);
      }
      std::complex<FloatType> gr(0);
      scitbx::vec3<std::complex<FloatType> > gr_site(0,0,0);
      std::complex<FloatType> gr_u_iso(0);
      scitbx::sym_mat3<FloatType> gr_u_cart(0,0,0,0,0,0);
      std::complex<FloatType> gr_occupancy(0);
      std::complex<FloatType> gr_fp(0);
      std::complex<FloatType> gr_fdp(0);
      grid_point_type pivot = detail::calc_nearest_grid_point(
        coor_frac, grid_f);
      // highly hand-optimized loop over points in shell
      grid_point_type g_min = pivot - shell.radii;
      grid_point_type g_max = pivot + shell.radii;
      grid_point_type gp;
      FloatType f0, f1, f2;
      FloatType c00, c01, c11;
      for(gp[0] = g_min[0]; gp[0] <= g_max[0]; gp[0]++) {
        f0 = FloatType(gp[0]) / grid_f[0] - coor_frac[0];
        c00 = orth_mx[0] * f0;
      for(gp[1] = g_min[1]; gp[1] <= g_max[1]; gp[1]++) {
        f1 = FloatType(gp[1]) / grid_f[1] - coor_frac[1];
        c01 = orth_mx[1] * f1 + c00;
        c11 = orth_mx[4] * f1;
      for(gp[2] = g_min[2]; gp[2] <= g_max[2]; gp[2]++) {
        f2 = FloatType(gp[2]) / grid_f[2] - coor_frac[2];
        scitbx::vec3<FloatType> d(
          orth_mx[2] * f2 + c01,
          orth_mx[5] * f2 + c11,
          orth_mx[8] * f2);
        FloatType d_sq = d.length_sq();
        if (d_sq > shell.max_d_sq) continue;
        if (!lifchitz) {
          FloatType r;
          if (!scatterer->anisotropic_flag) {
            r = caasf_ft.rho_real(d_sq);
          }
          else {
            r = caasf_ft.rho_real(d);
          }
          gr += ft_dt(gp) * r;
        }
        else {
          std::complex<FloatType> f = ft_dt(gp);
          scitbx::vec3<FloatType>
            drds_real = caasf_ft.d_rho_real_d_site(d, d_sq)
                      * unit_cell_.orthogonalization_matrix();
          if (!fdp) {
            for(std::size_t i=0;i<3;i++) {
              gr_site[i] += f * drds_real[i];
            }
          }
          else {
            scitbx::vec3<FloatType>
              drds_imag = caasf_ft.d_rho_imag_d_site(d, d_sq)
                        * unit_cell_.orthogonalization_matrix();
            for(std::size_t i=0;i<3;i++) {
              gr_site[i] += f * std::complex<FloatType>(
                drds_real[i], -drds_imag[i]);
            }
          }
          if (!scatterer->anisotropic_flag) {
            if (!fdp) {
              gr_u_iso += f * caasf_ft.d_rho_real_d_u_iso(d_sq);
            }
            else {
              gr_u_iso += f * std::complex<FloatType>(
                 caasf_ft.d_rho_real_d_u_iso(d_sq),
                -caasf_ft.d_rho_imag_d_u_iso(d_sq));
            }
          }
          else {
            scitbx::sym_mat3<FloatType>
              drdu_real = adptbx::u_as_b(caasf_ft.d_rho_real_d_b_cart(d));
            if (!fdp) {
              for(std::size_t i=0;i<6;i++) {
                gr_u_cart[i] += (f * drdu_real[i]).real();
              }
            }
            else {
              scitbx::sym_mat3<FloatType>
                drdu_imag = adptbx::u_as_b(caasf_ft.d_rho_imag_d_b_cart(d));
              for(std::size_t i=0;i<6;i++) {
                gr_u_cart[i] += (f * std::complex<FloatType>(
                   drdu_real[i],
                  -drdu_imag[i])).real();
              }
            }
          }
          FloatType drdo_real;
          if (!scatterer->anisotropic_flag) {
            drdo_real = caasf_ft.d_rho_real_d_occupancy(d_sq);
          }
          else {
            drdo_real = caasf_ft.d_rho_real_d_occupancy(d);
          }
          if (!fdp) {
            gr_occupancy += f * drdo_real;
          }
          else {
            FloatType drdo_imag;
            if (!scatterer->anisotropic_flag) {
              drdo_imag = caasf_ft.d_rho_imag_d_occupancy(d_sq);
            }
            else {
              drdo_imag = caasf_ft.d_rho_imag_d_occupancy(d);
            }
            gr_occupancy += f * std::complex<FloatType>(
                drdo_real, -drdo_imag);
          }
          if (!scatterer->anisotropic_flag) {
            gr_fp += f * caasf_ft.d_rho_real_d_fp(d_sq);
          }
          else {
            gr_fp += f * caasf_ft.d_rho_real_d_fp(d);
          }
          if (!scatterer->anisotropic_flag) {
            gr_fdp += f * std::complex<FloatType>(
              0, -caasf_ft.d_rho_imag_d_fdp(d_sq));
          }
          else {
            gr_fdp += f * std::complex<FloatType>(
              0, -caasf_ft.d_rho_imag_d_fdp(d));
          }
        }
      }}}
      if (!lifchitz) {
        grad_.push_back(gr);
      }
      else {
        grad_x_.push_back(gr_site[0]);
        grad_y_.push_back(gr_site[1]);
        grad_z_.push_back(gr_site[2]);
        if (!scatterer->anisotropic_flag) {
          grad_u_iso_.push_back(gr_u_iso);
        }
        else {
          scitbx::sym_mat3<FloatType>
            gr_u_star = adptbx::grad_u_cart_as_u_star(unit_cell_, gr_u_cart);
          grad_u_00_.push_back(gr_u_star[0]);
          grad_u_11_.push_back(gr_u_star[1]);
          grad_u_22_.push_back(gr_u_star[2]);
          grad_u_01_.push_back(gr_u_star[3]);
          grad_u_02_.push_back(gr_u_star[4]);
          grad_u_12_.push_back(gr_u_star[5]);
        }
        grad_occupancy_.push_back(gr_occupancy);
        grad_fp_.push_back(gr_fp);
        grad_fdp_.push_back(gr_fdp);
      }
    }
    exp_table_size_ = exp_table.table().size();
  }

}} // namespace cctbx::xray

#endif // CCTBX_XRAY_AGARWAL_1978_H
